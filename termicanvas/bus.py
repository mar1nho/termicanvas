"""Bus local — http.server stdlib + fila de mensagens com regra de entrega.

A regra de entrega segue o Maestri: mensagem so chega ao destinatario quando
ele esta idle (prompt detectado) E desselecionado (nao tem foco no canvas).
Isso evita pisar em digitacao manual do usuario humano.

Implementacao:
- HTTP server em thread separada (porta livre escolhida pelo OS)
- Fila in-memory de pendentes
- QTimer no UI thread (250ms) chama tick() que processa pendentes
- Cada terminal se registra com node_id, terminal_widget e frame
"""

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ._debug import snapshot
from .config import BUS_PORT_FILE, ensure_dirs


class _RegisteredNode:
    __slots__ = ("node_id", "name", "agent_kind", "terminal", "frame")

    def __init__(self, node_id, name, agent_kind, terminal, frame):
        self.node_id    = node_id
        self.name       = name
        self.agent_kind = agent_kind
        self.terminal   = terminal
        self.frame      = frame


class Bus(QObject):
    """Bus singleton-ish — instancia uma vez no main e passa adiante."""

    message_delivered = pyqtSignal(str, str, str)  # from, to, msg (telemetria)

    def __init__(self):
        super().__init__()
        self._nodes = {}            # node_id -> _RegisteredNode
        self._queue = []            # list[(from_id, to_id, message)]
        self._queue_lock = threading.Lock()
        self._server = None
        self._thread = None
        self._port   = None
        self._canvas = None         # injetado depois pra checar focado

        self._tick = QTimer(self)
        self._tick.setInterval(250)
        self._tick.timeout.connect(self._process_queue)

    # ---------- API publica ----------

    def start(self, canvas):
        self._canvas = canvas
        self._spin_server()
        self._tick.start()

    def stop(self):
        self._tick.stop()
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass

    def register(self, terminal, frame, name, agent_kind=None):
        node_id = uuid.uuid4().hex[:12]
        self._nodes[node_id] = _RegisteredNode(node_id, name, agent_kind, terminal, frame)
        return node_id

    def register_with_id(self, node_id, terminal, frame, name, agent_kind=None):
        """Registra usando um ID pre-definido (ex: ja injetado em env_extra)."""
        self._nodes[node_id] = _RegisteredNode(node_id, name, agent_kind, terminal, frame)

    def unregister(self, node_id):
        self._nodes.pop(node_id, None)

    def update_name(self, node_id, name):
        n = self._nodes.get(node_id)
        if n:
            n.name = name

    def port(self):
        return self._port

    def url(self):
        return f"http://127.0.0.1:{self._port}" if self._port else None

    def list_nodes(self):
        return [
            {"node_id": n.node_id, "name": n.name, "agent_kind": n.agent_kind}
            for n in self._nodes.values()
        ]

    def enqueue(self, from_id, to_id, message):
        with self._queue_lock:
            self._queue.append((from_id, to_id, message))

    # ---------- internals ----------

    def _spin_server(self):
        bus = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args, **_kw):
                return  # silencia stderr

            def do_GET(self):
                if self.path == "/list":
                    self._json(200, {"nodes": bus.list_nodes()})
                elif self.path == "/health":
                    self._json(200, {"ok": True})
                else:
                    self._json(404, {"error": "not found"})

            def do_POST(self):
                if self.path != "/send":
                    self._json(404, {"error": "not found"})
                    return
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(n).decode("utf-8")
                    data = json.loads(body)
                except Exception as e:
                    self._json(400, {"error": f"invalid body: {e}"})
                    return

                from_id = data.get("from", "")
                to_id   = data.get("to", "")
                message = data.get("message", "")
                if not to_id or not message:
                    self._json(400, {"error": "missing 'to' or 'message'"})
                    return
                if to_id not in bus._nodes:
                    self._json(404, {"error": f"unknown node: {to_id}"})
                    return

                bus.enqueue(from_id, to_id, message)
                self._json(202, {"queued": True})

            def _json(self, status, payload):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        # Persiste porta pra clientes externos (skill quando rodar fora do scope do env)
        ensure_dirs()
        try:
            BUS_PORT_FILE.write_text(str(self._port), encoding="utf-8")
        except Exception:
            pass

    def _process_queue(self):
        snapshot("tick", self)
        if not self._queue:
            return

        # Snapshot da fila pra processar fora do lock
        with self._queue_lock:
            pending = list(self._queue)
            self._queue.clear()

        focused_frame = getattr(self._canvas, "focused_frame", None) if self._canvas else None
        leftover = []

        for from_id, to_id, message in pending:
            target = self._nodes.get(to_id)
            if not target or not target.terminal or not target.terminal.alive:
                continue

            # Regra: idle E desselecionado
            is_focused = (target.frame is focused_frame)
            is_idle    = not bool(target.terminal.activity)

            if is_focused or not is_idle:
                leftover.append((from_id, to_id, message))
                continue

            # Entrega: injeta texto separado do Enter, com prefixo do emissor
            try:
                from_name = None
                src = self._nodes.get(from_id) if from_id else None
                if src:
                    from_name = src.name
                target.terminal.inject_message(
                    message, from_node_id=from_id, from_name=from_name,
                )
                self.message_delivered.emit(from_id, to_id, message)
            except Exception:
                leftover.append((from_id, to_id, message))

        if leftover:
            with self._queue_lock:
                # Repoe na frente preservando ordem original
                self._queue = leftover + self._queue


# ---------- helpers de cliente (usado pela CLI) ----------

def post_send(bus_url, from_id, to_id, message):
    payload = json.dumps(
        {"from": from_id, "to": to_id, "message": message}
    ).encode("utf-8")
    req = Request(
        f"{bus_url}/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


def get_list(bus_url):
    with urlopen(f"{bus_url}/list", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

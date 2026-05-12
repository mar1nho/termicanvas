"""Bus local — http.server stdlib + fila de mensagens com regra de entrega.

A regra de entrega segue o Maestri: mensagem so chega ao destinatario quando
ele esta idle (prompt detectado) E desselecionado (nao tem foco no canvas).
Isso evita pisar em digitacao manual do usuario humano.

Implementacao:
- HTTP server em thread separada (porta livre escolhida pelo OS)
- Fila in-memory de mensagens pendentes, cada uma com msg_id + created_at
- QTimer no UI thread (250ms) chama tick() que processa pendentes
- TTL padrao 300s: mensagens nao entregues expiram silenciosamente
- Cada terminal se registra com node_id, terminal_widget e frame

Endpoints HTTP:
- POST /send       {from, to, message}             -> {queued, msg_id}
- POST /broadcast  {from, message, exclude=[]}     -> {queued, msg_ids}
- POST /spawn      {kind, name, role_md, parent_cwd?} -> {accepted: True}
- GET  /list                                       -> {nodes: [...]}
- GET  /inbox?node_id=X                            -> {messages: [...]}
- GET  /status?msg_id=X                            -> {status: pending|delivered|expired}
- GET  /health                                     -> {ok: True}
"""

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .config import BUS_PORT_FILE, ensure_dirs


# TTL padrao em segundos — mensagens nao entregues sao removidas da fila.
DEFAULT_TTL = 300


class _RegisteredNode:
    __slots__ = ("node_id", "name", "agent_kind", "terminal", "frame")

    def __init__(self, node_id, name, agent_kind, terminal, frame):
        self.node_id    = node_id
        self.name       = name
        self.agent_kind = agent_kind
        self.terminal   = terminal
        self.frame      = frame


def _new_msg_id():
    return uuid.uuid4().hex[:10]


class Bus(QObject):
    """Bus singleton-ish — instancia uma vez no main e passa adiante."""

    message_delivered = pyqtSignal(str, str, str)   # from, to, msg (telemetria)
    spawn_requested   = pyqtSignal(dict)            # request dict (UI thread cria o terminal)

    def __init__(self, ttl=DEFAULT_TTL):
        super().__init__()
        self._nodes = {}            # node_id -> _RegisteredNode
        # Fila de pendentes — list de dicts (msg_id, from, to, message, created_at)
        self._queue = []
        # Track de mensagens ja processadas: msg_id -> status ("delivered"|"expired")
        self._delivered = {}
        self._queue_lock = threading.Lock()
        self._server = None
        self._thread = None
        self._port   = None
        self._canvas = None         # injetado depois pra checar focado
        self._ttl    = ttl

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
            except Exception as e:
                from .diagnostics import record_error
                record_error("bus.stop.server_shutdown", e)
            self._server = None
            self._thread = None
            self._port   = None
        self._nodes.clear()
        with self._queue_lock:
            self._queue.clear()
            self._delivered.clear()
        try:
            BUS_PORT_FILE.unlink(missing_ok=True)
        except Exception as e:
            from .diagnostics import record_error
            record_error("bus.stop.unlink", e)

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
        """Enfileira 1 mensagem. Retorna o msg_id gerado."""
        msg_id = _new_msg_id()
        item = {
            "msg_id":     msg_id,
            "from":       from_id,
            "to":         to_id,
            "message":    message,
            "created_at": time.time(),
        }
        with self._queue_lock:
            self._queue.append(item)
        return msg_id

    def broadcast(self, from_id, message, exclude=None):
        """Enfileira a mesma mensagem pra todos os nodes registrados (exceto
        from_id e excluidos). Retorna lista de msg_ids gerados."""
        exclude = set(exclude or [])
        if from_id:
            exclude.add(from_id)
        ids = []
        with self._queue_lock:
            for node_id in self._nodes.keys():
                if node_id in exclude:
                    continue
                msg_id = _new_msg_id()
                self._queue.append({
                    "msg_id":     msg_id,
                    "from":       from_id,
                    "to":         node_id,
                    "message":    message,
                    "created_at": time.time(),
                })
                ids.append(msg_id)
        return ids

    def inbox(self, node_id):
        """Lista mensagens pendentes pra um node especifico."""
        with self._queue_lock:
            return [
                {k: v for k, v in item.items()}
                for item in self._queue
                if item["to"] == node_id
            ]

    def status(self, msg_id):
        """Status de uma mensagem: pending, delivered, expired ou unknown."""
        with self._queue_lock:
            if msg_id in self._delivered:
                return self._delivered[msg_id]
            for item in self._queue:
                if item["msg_id"] == msg_id:
                    return "pending"
        return "unknown"

    # ---------- internals ----------

    def _spin_server(self):
        bus = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args, **_kw):
                return  # silencia stderr

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path
                qs   = parse_qs(parsed.query)
                if path == "/list":
                    self._json(200, {"nodes": bus.list_nodes()})
                elif path == "/health":
                    self._json(200, {"ok": True})
                elif path == "/inbox":
                    node_id = (qs.get("node_id") or [""])[0]
                    if not node_id:
                        self._json(400, {"error": "missing node_id"})
                        return
                    self._json(200, {"messages": bus.inbox(node_id)})
                elif path == "/status":
                    msg_id = (qs.get("msg_id") or [""])[0]
                    if not msg_id:
                        self._json(400, {"error": "missing msg_id"})
                        return
                    self._json(200, {"status": bus.status(msg_id)})
                else:
                    self._json(404, {"error": "not found"})

            def do_POST(self):
                parsed = urlparse(self.path)
                path = parsed.path
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(n).decode("utf-8")
                    data = json.loads(body) if body else {}
                except Exception as e:
                    self._json(400, {"error": f"invalid body: {e}"})
                    return

                if path == "/send":
                    self._handle_send(data)
                elif path == "/broadcast":
                    self._handle_broadcast(data)
                elif path == "/spawn":
                    self._handle_spawn(data)
                else:
                    self._json(404, {"error": "not found"})

            def _handle_send(self, data):
                from_id = data.get("from", "")
                to_id   = data.get("to", "")
                message = data.get("message", "")
                if not to_id or not message:
                    self._json(400, {"error": "missing 'to' or 'message'"})
                    return
                if to_id not in bus._nodes:
                    self._json(404, {"error": f"unknown node: {to_id}"})
                    return
                msg_id = bus.enqueue(from_id, to_id, message)
                self._json(202, {"queued": True, "msg_id": msg_id})

            def _handle_broadcast(self, data):
                from_id = data.get("from", "")
                message = data.get("message", "")
                exclude = data.get("exclude", []) or []
                if not message:
                    self._json(400, {"error": "missing 'message'"})
                    return
                msg_ids = bus.broadcast(from_id, message, exclude=exclude)
                self._json(202, {"queued": True, "msg_ids": msg_ids})

            def _handle_spawn(self, data):
                kind = data.get("kind", "")
                if kind not in ("claude", "gemini", "powershell", "cmd"):
                    self._json(400, {"error": f"invalid kind: {kind}"})
                    return
                if not data.get("name"):
                    self._json(400, {"error": "missing 'name'"})
                    return
                # Delega para a UI thread via signal (QueuedConnection automatica
                # entre threads diferentes).
                bus.spawn_requested.emit({
                    "kind":       kind,
                    "name":       data.get("name", ""),
                    "role_md":    data.get("role_md", ""),
                    "parent_cwd": data.get("parent_cwd", ""),
                    "from":       data.get("from", ""),
                })
                self._json(202, {"accepted": True})

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
        except Exception as e:
            from .diagnostics import record_error
            record_error("bus._spin_server.port_file", e)

    def _process_queue(self):
        if not self._queue:
            return

        now = time.time()

        # Snapshot da fila pra processar fora do lock
        with self._queue_lock:
            pending = list(self._queue)
            self._queue.clear()

        focused_frame = getattr(self._canvas, "focused_frame", None) if self._canvas else None
        leftover = []

        for item in pending:
            msg_id     = item["msg_id"]
            from_id    = item["from"]
            to_id      = item["to"]
            message    = item["message"]
            created_at = item["created_at"]

            # TTL: descarta mensagens antigas demais
            if (now - created_at) > self._ttl:
                self._delivered[msg_id] = "expired"
                continue

            target = self._nodes.get(to_id)
            if not target or not target.terminal or not target.terminal.alive:
                # Destinatario saiu — descarta
                self._delivered[msg_id] = "expired"
                continue

            # Regra: idle E desselecionado
            is_focused = (target.frame is focused_frame)
            is_idle    = not bool(target.terminal.activity)

            if is_focused or not is_idle:
                leftover.append(item)
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
                self._delivered[msg_id] = "delivered"
                self.message_delivered.emit(from_id, to_id, message)
            except Exception:
                leftover.append(item)

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


def post_broadcast(bus_url, from_id, message, exclude=None):
    payload = json.dumps(
        {"from": from_id, "message": message, "exclude": exclude or []}
    ).encode("utf-8")
    req = Request(
        f"{bus_url}/broadcast",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


def post_spawn(bus_url, from_id, kind, name, role_md="", parent_cwd=""):
    payload = json.dumps({
        "from":       from_id,
        "kind":       kind,
        "name":       name,
        "role_md":    role_md,
        "parent_cwd": parent_cwd,
    }).encode("utf-8")
    req = Request(
        f"{bus_url}/spawn",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


def get_list(bus_url):
    with urlopen(f"{bus_url}/list", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_inbox(bus_url, node_id):
    with urlopen(f"{bus_url}/inbox?node_id={node_id}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_status(bus_url, msg_id):
    with urlopen(f"{bus_url}/status?msg_id={msg_id}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

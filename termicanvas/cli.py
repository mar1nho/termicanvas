"""CLI de uso pelos agentes hospedados — chamada via `python -m termicanvas.cli`.

Uso:
    python -m termicanvas.cli send <node_id> "mensagem"
    python -m termicanvas.cli list
    python -m termicanvas.cli whoami

Le o bus pela env var TERMICANVAS_BUS_URL (setada quando o terminal foi spawnado).
Fallback: le porta de ~/.termicanvas/bus.port.
"""

import json
import os
import sys

from .bus import get_list, post_send
from .config import BUS_PORT_FILE


def _resolve_bus_url():
    url = os.environ.get("TERMICANVAS_BUS_URL")
    if url:
        return url
    if BUS_PORT_FILE.exists():
        try:
            port = BUS_PORT_FILE.read_text(encoding="utf-8").strip()
            if port:
                return f"http://127.0.0.1:{port}"
        except Exception:
            pass
    return None


def _whoami():
    return os.environ.get("TERMICANVAS_NODE_ID", "")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("uso: python -m termicanvas.cli {send|list|whoami}", file=sys.stderr)
        return 2

    cmd = argv[0]
    bus_url = _resolve_bus_url()
    if not bus_url and cmd != "whoami":
        print("[erro] TERMICANVAS_BUS_URL nao definida e bus.port nao encontrado.", file=sys.stderr)
        return 1

    if cmd == "whoami":
        print(_whoami())
        return 0

    if cmd == "list":
        try:
            data = get_list(bus_url)
        except Exception as e:
            print(f"[erro] falha ao listar nodes: {e}", file=sys.stderr)
            return 1
        for n in data.get("nodes", []):
            kind = n.get("agent_kind") or "shell"
            print(f"{n['node_id']}  [{kind:7}]  {n['name']}")
        return 0

    if cmd == "send":
        if len(argv) < 3:
            print("uso: python -m termicanvas.cli send <node_id> \"mensagem\"", file=sys.stderr)
            return 2
        to_id   = argv[1]
        message = " ".join(argv[2:])
        from_id = _whoami()
        try:
            status, body = post_send(bus_url, from_id, to_id, message)
        except Exception as e:
            print(f"[erro] falha ao enviar: {e}", file=sys.stderr)
            return 1
        if 200 <= status < 300:
            print(f"[ok] enfileirado para {to_id}")
            return 0
        print(f"[erro] {status}: {body}", file=sys.stderr)
        return 1

    print(f"[erro] comando desconhecido: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

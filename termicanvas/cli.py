"""CLI de uso pelos agentes hospedados — chamada via `python -m termicanvas.cli`.

Uso:
    python -m termicanvas.cli send <node_id> "mensagem"
    python -m termicanvas.cli broadcast "mensagem"
    python -m termicanvas.cli spawn <kind> <nome> [--parent-cwd <path>]
        (le role_md do stdin se houver, senao usa default minimo)
    python -m termicanvas.cli list
    python -m termicanvas.cli inbox
    python -m termicanvas.cli status <msg_id>
    python -m termicanvas.cli whoami

Le o bus pela env var TERMICANVAS_BUS_URL (setada quando o terminal foi spawnado).
Fallback: le porta de ~/.termicanvas/bus.port.
"""

import os
import select
import sys

from .bus import (
    get_inbox,
    get_list,
    get_status,
    post_broadcast,
    post_send,
    post_spawn,
)
from .config import BUS_PORT_FILE


USAGE = (
    "uso: python -m termicanvas.cli {send|broadcast|spawn|list|inbox|status|whoami}"
)


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


def _read_stdin_if_available():
    """Le todo o stdin se houver dado disponivel (nao bloqueia se nao tiver).
    Forca UTF-8 — no Windows o default e cp1252 e corrompe acentos."""
    try:
        if sys.stdin.isatty():
            return ""
        if hasattr(sys.stdin, "buffer"):
            raw = sys.stdin.buffer.read()
            return raw.decode("utf-8", errors="replace")
        return sys.stdin.read()
    except Exception:
        return ""


def _cmd_list(bus_url):
    try:
        data = get_list(bus_url)
    except Exception as e:
        print(f"[erro] falha ao listar nodes: {e}", file=sys.stderr)
        return 1
    for n in data.get("nodes", []):
        kind = n.get("agent_kind") or "shell"
        print(f"{n['node_id']}  [{kind:7}]  {n['name']}")
    return 0


def _cmd_send(bus_url, argv):
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
        print(body)
        return 0
    print(f"[erro] {status}: {body}", file=sys.stderr)
    return 1


def _cmd_broadcast(bus_url, argv):
    if len(argv) < 2:
        print("uso: python -m termicanvas.cli broadcast \"mensagem\"", file=sys.stderr)
        return 2
    message = " ".join(argv[1:])
    from_id = _whoami()
    try:
        status, body = post_broadcast(bus_url, from_id, message)
    except Exception as e:
        print(f"[erro] falha no broadcast: {e}", file=sys.stderr)
        return 1
    if 200 <= status < 300:
        print(body)
        return 0
    print(f"[erro] {status}: {body}", file=sys.stderr)
    return 1


def _cmd_spawn(bus_url, argv):
    if len(argv) < 3:
        print(
            "uso: python -m termicanvas.cli spawn <kind> \"<nome>\" "
            "[--parent-cwd <path>] [--role-file <path>]\n"
            "    kind: claude | gemini | codex | powershell | cmd\n"
            "    role_md vem de --role-file (preferido) ou stdin",
            file=sys.stderr,
        )
        return 2
    kind = argv[1]
    name = argv[2]
    parent_cwd = ""
    if "--parent-cwd" in argv:
        i = argv.index("--parent-cwd")
        if i + 1 < len(argv):
            parent_cwd = argv[i + 1]

    # role_md: --role-file tem prioridade sobre stdin. Util pra agentes que
    # batem no limite de parser de comandos (965 bytes no Claude Code) — o
    # agente escreve o role num arquivo .md primeiro e referencia aqui.
    role_md = ""
    if "--role-file" in argv:
        i = argv.index("--role-file")
        if i + 1 < len(argv):
            from pathlib import Path
            try:
                role_md = Path(argv[i + 1]).read_text(encoding="utf-8")
            except Exception as e:
                print(f"[erro] falha ao ler role-file: {e}", file=sys.stderr)
                return 1
    if not role_md:
        role_md = _read_stdin_if_available()
    from_id = _whoami()
    try:
        status, body = post_spawn(bus_url, from_id, kind, name, role_md, parent_cwd)
    except Exception as e:
        print(f"[erro] falha no spawn: {e}", file=sys.stderr)
        return 1
    if 200 <= status < 300:
        print(body)
        return 0
    print(f"[erro] {status}: {body}", file=sys.stderr)
    return 1


def _cmd_inbox(bus_url):
    node_id = _whoami()
    if not node_id:
        print("[erro] TERMICANVAS_NODE_ID nao definida.", file=sys.stderr)
        return 1
    try:
        data = get_inbox(bus_url, node_id)
    except Exception as e:
        print(f"[erro] falha ao ler inbox: {e}", file=sys.stderr)
        return 1
    messages = data.get("messages", [])
    if not messages:
        print("(inbox vazia)")
        return 0
    for m in messages:
        print(f"[{m['msg_id']}] de {m['from'] or '?'}: {m['message']}")
    return 0


def _cmd_status(bus_url, argv):
    if len(argv) < 2:
        print("uso: python -m termicanvas.cli status <msg_id>", file=sys.stderr)
        return 2
    msg_id = argv[1]
    try:
        data = get_status(bus_url, msg_id)
    except Exception as e:
        print(f"[erro] falha ao consultar status: {e}", file=sys.stderr)
        return 1
    print(data.get("status", "unknown"))
    return 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2

    cmd = argv[0]

    if cmd == "whoami":
        print(_whoami())
        return 0

    bus_url = _resolve_bus_url()
    if not bus_url:
        print("[erro] TERMICANVAS_BUS_URL nao definida e bus.port nao encontrado.", file=sys.stderr)
        return 1

    if cmd == "list":
        return _cmd_list(bus_url)
    if cmd == "send":
        return _cmd_send(bus_url, argv)
    if cmd == "broadcast":
        return _cmd_broadcast(bus_url, argv)
    if cmd == "spawn":
        return _cmd_spawn(bus_url, argv)
    if cmd == "inbox":
        return _cmd_inbox(bus_url)
    if cmd == "status":
        return _cmd_status(bus_url, argv)

    print(f"[erro] comando desconhecido: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

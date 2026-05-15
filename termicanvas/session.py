"""Persistencia da sessao (nodes, conexoes, viewport) em session.json.

A funcao serialize_canvas() e exportada para que o modulo snapshots.py
reuse a mesma logica sem duplicar codigo.
"""

import json

from .agent import AgentWidget
from .config import SESSION_FILE, get_default_cwd
from .preview import PreviewWidget
from .terminal import TerminalWidget
from .tokens import ACCENT
from .widgets import NoteWidget, PromptCard


def serialize_canvas(canvas):
    """Converte o estado atual do canvas em (nodes, connections) JSON-able.

    nodes: list[dict] — cada um com type/name/icon/x/y/w/h/color e fields
    especificos do tipo (terminal -> shell/cwd/agent_kind/etc; note -> content;
    prompt -> content; agent/debug_monitor -> sem extras).

    connections: list[[src_idx, tgt_idx]] — indices em canvas.proxies.
    """
    nodes = []
    for proxy, frame in canvas.proxies:
        pos = proxy.pos()
        # Cor por node nao e mais persistida — todos herdam a accent global no load.
        base = {
            "name": frame.header.title.text(),
            "icon": frame.icon_text() if hasattr(frame, "icon_text") else "",
            "x":    pos.x(),
            "y":    pos.y(),
            "w":    frame.width(),
            "h":    frame.height(),
            "compacted": getattr(frame, "_compacted", False) is True,
        }
        if isinstance(frame.inner, TerminalWidget):
            base.update({
                "type":          "terminal",
                "shell":         frame.inner.shell,
                "cwd":           frame.inner.cwd or get_default_cwd(),
                "font_size":     frame.inner._font_size,
                "agent_kind":    frame.inner.agent_kind,
                "role_name":     frame.inner.role_name,
                "manifest_mode": frame.inner.manifest_mode,
                "owned_cwd":     bool(getattr(frame.inner, "owned_cwd", False)),
            })
        elif isinstance(frame.inner, NoteWidget):
            base.update({"type": "note", "content": frame.inner.toPlainText()})
        elif isinstance(frame.inner, AgentWidget):
            base.update({"type": "agent"})
        elif isinstance(frame.inner, PromptCard):
            base.update({"type": "prompt", "content": frame.inner.text()})
        elif isinstance(frame.inner, PreviewWidget):
            base.update({
                "type": "preview",
                "path": frame.inner.path,
                "mode": frame.inner.mode,
            })
        else:
            from .monitor import DebugMonitorWidget
            if isinstance(frame.inner, DebugMonitorWidget):
                base.update({"type": "debug_monitor"})
            else:
                continue
        nodes.append(base)

    frame_list = [f for _, f in canvas.proxies]
    conns = []
    for src, tgt in canvas.connections:
        try:
            conns.append([frame_list.index(src), frame_list.index(tgt)])
        except ValueError:
            pass
    chains = []
    for parent, child in getattr(canvas, "chains", []):
        try:
            chains.append([frame_list.index(parent), frame_list.index(child)])
        except ValueError:
            pass
    return nodes, conns, chains


def save_session(canvas, accent_color=ACCENT, bus_enabled=False, bus_toggle_warned=False,
                 snapshot_load_warned=False, light_mode=False, default_cwd=None):
    nodes, conns, chains = serialize_canvas(canvas)
    canvas_data = {
        "scale":                 canvas.transform().m11(),
        "scroll_h":              canvas.horizontalScrollBar().value(),
        "scroll_v":              canvas.verticalScrollBar().value(),
        "accent_color":          accent_color,
        "bus_enabled":           bool(bus_enabled),
        "bus_toggle_warned":     bool(bus_toggle_warned),
        "snapshot_load_warned":  bool(snapshot_load_warned),
        "light_mode":            bool(light_mode),
        "default_cwd":            default_cwd or get_default_cwd(),
    }
    data = {
        "canvas":        canvas_data,
        "nodes":         nodes,
        "connections":   conns,
        "chains":        chains,
    }
    try:
        SESSION_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def load_session():
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None

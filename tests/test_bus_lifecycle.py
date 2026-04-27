"""Regression test: closing a terminal node must remove it from the Bus registry."""

from unittest.mock import MagicMock
import pytest

from PyQt6.QtWidgets import QApplication

from termicanvas.bus import Bus
from termicanvas.terminal import TerminalWidget


@pytest.fixture(scope="module")
def qt_app():
    """Bus uses QObject + QTimer, and the canvas instrumentation walks
    QApplication.allWidgets(), so we need a full QApplication."""
    app = QApplication.instance() or QApplication([])
    yield app


def test_unregister_removes_node(qt_app):
    bus = Bus()
    fake_terminal = MagicMock()
    fake_terminal.alive = True
    fake_frame = MagicMock()

    bus.register_with_id("abc123", fake_terminal, fake_frame, "Term A")
    assert "abc123" in bus._nodes

    bus.unregister("abc123")
    assert "abc123" not in bus._nodes


def test_close_calls_unregister(qt_app, monkeypatch):
    """Validates the contract: when CanvasView._close runs on a frame whose
    inner is a TerminalWidget, it MUST call self._bus_ref.unregister(node_id)
    exactly once with the terminal's node_id."""
    from termicanvas.canvas import CanvasView

    bus = Bus()
    unregister_calls = []
    monkeypatch.setattr(bus, "unregister", lambda nid: unregister_calls.append(nid))

    # MagicMock(spec=TerminalWidget) makes isinstance(mock, TerminalWidget) return True
    # — that's exactly what we need for the isinstance check inside _close.
    fake_terminal = MagicMock(spec=TerminalWidget)
    fake_terminal.node_id = "xyz789"
    fake_terminal.alive = True

    fake_frame = MagicMock()
    fake_frame.inner = fake_terminal

    fake_proxy = MagicMock()

    # Build a stand-in for the canvas with only the attributes _close touches.
    # We don't need a real CanvasView — we just call the unbound method with our
    # stand-in as self, exercising the actual code path.
    canvas = MagicMock()
    canvas.proxies = [(fake_proxy, fake_frame)]
    canvas.connections = []
    canvas.focused_frame = None
    canvas._bus_ref = bus

    CanvasView._close(canvas, fake_frame)

    assert unregister_calls == ["xyz789"], (
        f"expected exactly one unregister call with 'xyz789', got {unregister_calls}"
    )
    assert canvas.proxies == [], "proxy should be removed from canvas.proxies"

"""Tests for the bus toggle feature."""

import json

import pytest
from PyQt6.QtWidgets import QApplication

from termicanvas.session import load_session, save_session


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_save_session_persists_bus_flags(qt_app, tmp_path, monkeypatch):
    """save_session must write bus_enabled and bus_toggle_warned in canvas section."""
    from termicanvas import session as session_mod
    fake_path = tmp_path / "session.json"
    monkeypatch.setattr(session_mod, "SESSION_FILE", fake_path)

    class FakeCanvas:
        proxies = []
        connections = []
        def transform(self):
            class T:
                def m11(self): return 1.0
            return T()
        def horizontalScrollBar(self):
            class S:
                def value(self): return 0
            return S()
        def verticalScrollBar(self):
            class S:
                def value(self): return 0
            return S()

    save_session(FakeCanvas(), "#5a8dff", bus_enabled=False, bus_toggle_warned=True)

    data = json.loads(fake_path.read_text(encoding="utf-8"))
    assert data["canvas"]["bus_enabled"] is False
    assert data["canvas"]["bus_toggle_warned"] is True


def test_load_session_legacy_has_no_bus_flags(qt_app, tmp_path, monkeypatch):
    """Legacy session.json without the new fields loads cleanly."""
    from termicanvas import session as session_mod
    fake_path = tmp_path / "session.json"
    fake_path.write_text(json.dumps({
        "canvas": {"scale": 1.0, "scroll_h": 0, "scroll_v": 0, "accent_color": "#5a8dff"},
        "nodes": [],
        "connections": [],
    }), encoding="utf-8")
    monkeypatch.setattr(session_mod, "SESSION_FILE", fake_path)

    data = load_session()
    assert "bus_enabled" not in data["canvas"]
    assert "bus_toggle_warned" not in data["canvas"]


def test_bus_off_dialog_returns_confirmed_and_dont_ask(qt_app):
    from termicanvas.dialogs import BusOffConfirmDialog

    dlg = BusOffConfirmDialog()
    # default state
    assert dlg.dont_ask_again() is False

    dlg._dont_ask.setChecked(True)
    assert dlg.dont_ask_again() is True


def test_bus_off_dialog_has_cancel_and_confirm_buttons(qt_app):
    from termicanvas.dialogs import BusOffConfirmDialog

    dlg = BusOffConfirmDialog()
    assert dlg._cancel_btn.text().lower() == "cancelar"
    assert "desligar" in dlg._confirm_btn.text().lower()


def test_bus_off_dialog_buttons_resolve_correctly(qt_app):
    """Cancel must produce Rejected; Desligar must produce Accepted.
    Task 6's _show_bus_off_confirmation depends on this contract."""
    from PyQt6.QtWidgets import QDialog
    from termicanvas.dialogs import BusOffConfirmDialog

    cancel_dlg = BusOffConfirmDialog()
    cancel_dlg._cancel_btn.click()
    assert cancel_dlg.result() == QDialog.DialogCode.Rejected

    confirm_dlg = BusOffConfirmDialog()
    confirm_dlg._confirm_btn.click()
    assert confirm_dlg.result() == QDialog.DialogCode.Accepted


def test_canvas_clear_all_removes_proxies_and_connections(qt_app):
    from unittest.mock import MagicMock
    from termicanvas.canvas import CanvasView
    from termicanvas.terminal import TerminalWidget

    canvas = CanvasView()

    # Two terminal-like nodes + one connection between them.
    fake_terminal_a = MagicMock(spec=TerminalWidget)
    fake_terminal_a.node_id = "aaa"
    fake_terminal_b = MagicMock(spec=TerminalWidget)
    fake_terminal_b.node_id = "bbb"

    proxy_a, frame_a = MagicMock(), MagicMock()
    frame_a.inner = fake_terminal_a
    proxy_b, frame_b = MagicMock(), MagicMock()
    frame_b.inner = fake_terminal_b

    canvas.proxies = [(proxy_a, frame_a), (proxy_b, frame_b)]
    canvas.connections = [(frame_a, frame_b)]
    canvas.focused_frame = frame_a

    fake_bus = MagicMock()

    canvas.clear_all(bus=fake_bus)

    assert canvas.proxies == []
    assert canvas.connections == []
    assert canvas.focused_frame is None
    fake_terminal_a.shutdown.assert_called_once()
    fake_terminal_b.shutdown.assert_called_once()
    fake_bus.unregister.assert_any_call("aaa")
    fake_bus.unregister.assert_any_call("bbb")


def test_canvas_clear_all_emits_nodes_changed(qt_app):
    from termicanvas.canvas import CanvasView

    canvas = CanvasView()
    fired = []
    canvas.nodes_changed.connect(lambda: fired.append(True))

    canvas.clear_all()

    assert fired == [True]


def test_canvas_clear_all_swallows_shutdown_errors(qt_app):
    from unittest.mock import MagicMock
    from termicanvas.canvas import CanvasView
    from termicanvas.terminal import TerminalWidget

    canvas = CanvasView()
    bad = MagicMock(spec=TerminalWidget)
    bad.node_id = "x"
    bad.shutdown.side_effect = RuntimeError("boom")
    proxy, frame = MagicMock(), MagicMock()
    frame.inner = bad
    canvas.proxies = [(proxy, frame)]

    # must not raise
    canvas.clear_all(bus=MagicMock())
    assert canvas.proxies == []


def test_bus_toggle_button_default_state_is_on(qt_app):
    from termicanvas.topbar import BusToggleButton

    btn = BusToggleButton()
    assert btn._state is True
    assert "ligado" in btn.toolTip().lower()


def test_bus_toggle_button_set_state_updates_tooltip_and_animation(qt_app):
    from termicanvas.topbar import BusToggleButton
    from PyQt6.QtCore import QAbstractAnimation

    btn = BusToggleButton()
    btn.set_state(False)
    assert btn._state is False
    assert "desligado" in btn.toolTip().lower()
    assert btn._anim.state() == QAbstractAnimation.State.Running

    btn.set_state(True)
    assert btn._state is True
    assert btn._anim.state() == QAbstractAnimation.State.Stopped


def test_bus_toggle_button_emits_clicked_signal(qt_app):
    """Default state is ON; pressing emits clicked(False) — the new requested state."""
    from termicanvas.topbar import BusToggleButton

    btn = BusToggleButton()
    fired = []
    btn.clicked.connect(lambda new_state: fired.append(new_state))

    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    ev = QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(12, 12), Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    btn.mousePressEvent(ev)
    # default _state is True, so the click requests the inverse: False.
    assert fired == [False]


def test_topbar_emits_bus_toggled_with_inverse_of_current_state(qt_app):
    """The clicked signal now carries the requested state directly; TopBar
    forwards it as bus_toggled(bool)."""
    from termicanvas.topbar import TopBar

    bar = TopBar()
    received = []
    bar.bus_toggled.connect(lambda enabled: received.append(enabled))

    # default state is True; click should request False
    bar._bus_button.clicked.emit(False)
    assert received == [False]

    # now flip to off, then click should request True
    bar.set_bus_state(False)
    bar._bus_button.clicked.emit(True)
    assert received == [False, True]

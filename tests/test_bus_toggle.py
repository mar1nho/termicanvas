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

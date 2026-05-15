"""Tests for InsertController state machine + canvas integration."""

import pytest
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_initial_state_is_idle(qt_app):
    from termicanvas.insert_controller import InsertController, InsertState
    c = InsertController()
    assert c.state == InsertState.IDLE
    assert c.armed_kind is None


def test_arm_transitions_to_armed(qt_app):
    from termicanvas.insert_controller import InsertController, InsertState
    c = InsertController()
    c.arm("powershell", with_dialog=False)
    assert c.state == InsertState.ARMED
    assert c.armed_kind == "powershell"
    assert c.with_dialog is False


def test_arm_with_dialog_flag(qt_app):
    from termicanvas.insert_controller import InsertController
    c = InsertController()
    c.arm("claude", with_dialog=True)
    assert c.with_dialog is True


def test_re_arm_same_kind_disarms(qt_app):
    from termicanvas.insert_controller import InsertController, InsertState
    c = InsertController()
    c.arm("note", with_dialog=False)
    c.arm("note", with_dialog=False)
    assert c.state == InsertState.IDLE


def test_arm_different_kind_switches(qt_app):
    from termicanvas.insert_controller import InsertController
    c = InsertController()
    c.arm("note")
    c.arm("prompt")
    assert c.armed_kind == "prompt"


def test_start_drag_only_when_armed(qt_app):
    from termicanvas.insert_controller import InsertController, InsertState
    c = InsertController()
    c.start_drag(QPointF(10, 10))
    assert c.state == InsertState.IDLE
    c.arm("note")
    c.start_drag(QPointF(10, 10))
    assert c.state == InsertState.DRAGGING
    assert c.drag_origin == QPointF(10, 10)


def test_finish_drag_emits_commit_with_geometry(qt_app):
    from termicanvas.insert_controller import InsertController
    c = InsertController()
    received = []
    c.commit_requested.connect(
        lambda kind, rect, with_dlg: received.append((kind, rect, with_dlg))
    )
    c.arm("note", with_dialog=False)
    c.start_drag(QPointF(50, 80))
    c.update_drag(QPointF(450, 380))
    c.finish_drag(QPointF(450, 380))
    assert len(received) == 1
    kind, rect, with_dlg = received[0]
    assert kind == "note"
    assert isinstance(rect, QRectF)
    assert rect.x() == 50 and rect.y() == 80
    assert rect.width() == 400 and rect.height() == 300


def test_click_without_drag_emits_commit_with_zero_rect(qt_app):
    from termicanvas.insert_controller import InsertController
    c = InsertController()
    received = []
    c.commit_requested.connect(lambda *args: received.append(args))
    c.arm("note")
    c.start_drag(QPointF(100, 100))
    c.finish_drag(QPointF(100, 100))
    assert len(received) == 1
    rect = received[0][1]
    assert rect.width() == 0 and rect.height() == 0


def test_disarm_resets(qt_app):
    from termicanvas.insert_controller import InsertController, InsertState
    c = InsertController()
    c.arm("note")
    c.start_drag(QPointF(10, 10))
    c.disarm()
    assert c.state == InsertState.IDLE
    assert c.armed_kind is None


def test_canvas_insert_mode_activates_cursor(qt_app, monkeypatch, tmp_path):
    from termicanvas import session as session_mod, config as config_mod
    monkeypatch.setattr(session_mod, "SESSION_FILE", tmp_path / "session.json")
    config_mod.set_default_cwd(str(tmp_path))
    from main import MainWindow
    w = MainWindow()
    w.canvas.set_insert_active(True)
    assert w.canvas._insert_active is True
    w.canvas.set_insert_active(False)
    assert w.canvas._insert_active is False
    assert w.canvas._drag_preview is None
    w.close()


def test_drag_preview_snaps_to_grid(qt_app, monkeypatch, tmp_path):
    from termicanvas import session as session_mod, config as config_mod
    monkeypatch.setattr(session_mod, "SESSION_FILE", tmp_path / "session.json")
    config_mod.set_default_cwd(str(tmp_path))
    from main import MainWindow
    w = MainWindow()
    w.canvas.set_insert_active(True)
    w.canvas.show_drag_preview(QRectF(13, 27, 250, 195))
    item = w.canvas._drag_preview
    rect = item.rect()
    assert rect.x() == 0 and rect.y() == 40
    assert rect.width() == 240 and rect.height() == 200
    w.close()

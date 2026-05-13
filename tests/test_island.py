"""Tests for ToolIsland widget."""

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_island_has_eight_buttons(qt_app):
    from termicanvas.island import ToolIsland
    island = ToolIsland()
    assert len(island.buttons) == 8
    kinds = [b.kind for b in island.buttons]
    assert kinds == ["powershell", "cmd", "claude", "gemini", "note", "prompt", "agent", "debug"]


def test_click_emits_tool_armed_without_dialog(qt_app):
    from termicanvas.island import ToolIsland
    island = ToolIsland()
    received = []
    island.tool_armed.connect(lambda k, d: received.append((k, d)))
    island.buttons[0]._emit_armed(with_dialog=False)
    assert received == [("powershell", False)]


def test_shift_click_emits_tool_armed_with_dialog(qt_app):
    from termicanvas.island import ToolIsland
    island = ToolIsland()
    received = []
    island.tool_armed.connect(lambda k, d: received.append((k, d)))
    island.buttons[2]._emit_armed(with_dialog=True)
    assert received == [("claude", True)]


def test_double_click_emits_tool_doubled(qt_app):
    from termicanvas.island import ToolIsland
    island = ToolIsland()
    doubled = []
    island.tool_doubled.connect(lambda k: doubled.append(k))
    island.buttons[4]._emit_doubled()
    assert doubled == ["note"]


def test_set_armed_kind_highlights_button(qt_app):
    from termicanvas.island import ToolIsland
    island = ToolIsland()
    island.set_armed_kind("note")
    assert island.buttons[4].is_armed is True
    assert all(not b.is_armed for b in island.buttons if b.kind != "note")
    island.set_armed_kind(None)
    assert all(not b.is_armed for b in island.buttons)


def test_mouse_press_with_shift_modifier_routes_to_dialog(qt_app):
    from termicanvas.island import ToolIsland
    island = ToolIsland()
    received = []
    island.tool_armed.connect(lambda k, d: received.append((k, d)))
    btn = island.buttons[0]
    ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(5, 5), QPointF(5, 5),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    btn.mousePressEvent(ev)
    assert received == [("powershell", True)]

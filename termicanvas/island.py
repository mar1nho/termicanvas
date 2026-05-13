"""ToolIsland: floating toolbar for creating nodes."""

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from .icons import get_icon
from .tokens import ACCENT, TEXT_PRIMARY, TEXT_SECONDARY


TOOLS = [
    ("powershell", "terminal_ps", "PowerShell", 0),
    ("cmd", "terminal_cmd", "CMD", 0),
    ("claude", "agent_claude", "Claude", 0),
    ("gemini", "agent_gemini", "Gemini", 0),
    ("note", "edit", "Nota", 1),
    ("prompt", "clipboard", "Prompt", 1),
    ("agent", "agent_code", "Agent", 1),
    ("debug", "bug", "Debug Monitor", 1),
]


class IconButton(QPushButton):
    armed = pyqtSignal(str, bool)
    doubled = pyqtSignal(str)

    def __init__(self, kind, icon_name, label):
        super().__init__()
        self.kind = kind
        self._icon_name = icon_name
        self.is_armed = False
        self._light_mode = False
        self.setFixedSize(28, 28)
        self.setIconSize(QSize(16, 16))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{label} - clique pra criar - shift-clique pro dialog")
        self.setAccessibleName(label)
        self._refresh_icon()
        self._apply_style()

    def _refresh_icon(self):
        """Atualiza icone conforme tema + estado armed."""
        if self.is_armed:
            color = TEXT_PRIMARY if not self._light_mode else "#1a1a1a"
        else:
            color = TEXT_SECONDARY if not self._light_mode else "#3a3a3a"
        self.setIcon(get_icon(self._icon_name, color=color, size=16))

    def _apply_style(self):
        if self.is_armed:
            bg = f"rgba({self._hex_to_rgb(ACCENT)}, 0.15)"
            border = ACCENT
        else:
            bg = "transparent"
            border = "transparent"
        hover_bg = "rgba(255, 255, 255, 0.05)" if not self._light_mode else "rgba(0, 0, 0, 0.06)"
        hover_border = "rgba(255, 255, 255, 0.10)" if not self._light_mode else "rgba(0, 0, 0, 0.10)"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {hover_bg};
                border-color: {hover_border};
            }}
        """)

    def set_light_mode(self, enabled: bool):
        self._light_mode = bool(enabled)
        self._refresh_icon()
        self._apply_style()

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> str:
        h = hex_color.lstrip("#")
        return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"

    def set_armed(self, armed: bool):
        if self.is_armed == armed:
            return
        self.is_armed = armed
        self._refresh_icon()
        self._apply_style()

    def _emit_armed(self, with_dialog: bool):
        self.armed.emit(self.kind, with_dialog)

    def _emit_doubled(self):
        self.doubled.emit(self.kind)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._emit_armed(with_dialog=True)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            with_dialog = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._emit_armed(with_dialog=with_dialog)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._emit_doubled()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class ToolIsland(QWidget):
    tool_armed = pyqtSignal(str, bool)
    tool_doubled = pyqtSignal(str)
    user_moved = pyqtSignal()

    HEIGHT = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(self.HEIGHT)
        self._dragging = False
        self._drag_start_global = QPoint()
        self._drag_start_pos = QPoint()
        self._light_mode = False
        self.setCursor(Qt.CursorShape.SizeAllCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        self.buttons = []
        last_group = 0
        for kind, icon_name, label, group in TOOLS:
            if group != last_group:
                layout.addSpacing(8)
                last_group = group
            btn = IconButton(kind, icon_name, label)
            btn.armed.connect(self.tool_armed.emit)
            btn.doubled.connect(self.tool_doubled.emit)
            layout.addWidget(btn)
            self.buttons.append(btn)

        self.adjustSize()

    def set_armed_kind(self, kind):
        for b in self.buttons:
            b.set_armed(b.kind == kind)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_pos = self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.globalPosition().toPoint() - self._drag_start_global
            target = self._drag_start_pos + delta
            parent = self.parentWidget()
            if parent is not None:
                max_x = max(0, parent.width() - self.width())
                max_y = max(0, parent.height() - self.height())
                target.setX(max(0, min(target.x(), max_x)))
                target.setY(max(0, min(target.y(), max_y)))
            self.move(target)
            self.user_moved.emit()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_light_mode(self, enabled: bool):
        """Adapta gradient + icones do island ao tema."""
        self._light_mode = bool(enabled)
        for btn in self.buttons:
            btn.set_light_mode(self._light_mode)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 16, 16)

        grad = QLinearGradient(0, 0, 0, rect.height())
        if self._light_mode:
            grad.setColorAt(0.0, QColor(240, 240, 240, 220))
            grad.setColorAt(1.0, QColor(220, 220, 220, 220))
            border_color = QColor(0, 0, 0, 40)
            divider_color = QColor(0, 0, 0, 30)
        else:
            grad.setColorAt(0.0, QColor(48, 48, 48, 190))
            grad.setColorAt(1.0, QColor(34, 34, 34, 190))
            border_color = QColor(255, 255, 255, 36)
            divider_color = QColor(255, 255, 255, 18)
        p.fillPath(path, grad)

        p.setPen(border_color)
        p.drawPath(path)

        if len(self.buttons) >= 5:
            divider_x = (self.buttons[3].geometry().right() + self.buttons[4].geometry().left()) // 2
            p.setPen(divider_color)
            p.drawLine(divider_x, 8, divider_x, self.height() - 8)

        p.end()

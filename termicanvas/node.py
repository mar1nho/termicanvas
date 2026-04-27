"""NodeHeader, ResizeGrip, NodeFrame: chrome dos cards no canvas."""

from PyQt6.QtCore import QEvent, QPointF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import get_icon
from .tokens import (
    ACCENT,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER,
    BORDER_HOVER,
    DANGER,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    safe_border_color,
)
from .widgets import EditableLabel


class NodeHeader(QWidget):
    drag_moved      = pyqtSignal(QPointF)
    close_clicked   = pyqtSignal()
    focus_requested = pyqtSignal()
    title_changed   = pyqtSignal(str)
    icon_changed    = pyqtSignal(str)
    font_up_clicked   = pyqtSignal()
    font_down_clicked = pyqtSignal()
    color_picked      = pyqtSignal(str)
    edit_role_clicked = pyqtSignal()
    auto_reply_toggled = pyqtSignal(bool)

    def __init__(self, title, icon=""):
        super().__init__()
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._dragging     = False
        self._last_global  = None
        self._accent_color = ACCENT
        self._is_focused   = False  # alimenta o indicador idle/ativo
        self._apply_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(10)

        self.dot = QLabel("●")
        layout.addWidget(self.dot)
        self._refresh_dot()

        self.icon = EditableLabel(icon)
        self.icon.set_label_style(
            f"QLabel {{ color: {TEXT_PRIMARY}; font-family: 'Segoe UI';"
            f"font-size: 11pt; background: transparent; padding: 0px; }}"
        )
        self.icon.setFixedWidth(28 if icon else 0)
        if not icon:
            self.icon.setHidden(True)
        self.icon.text_changed.connect(self._on_icon_changed)
        layout.addWidget(self.icon)

        self.title = EditableLabel(title)
        self.title.set_label_style(
            f"QLabel {{ color: {TEXT_SECONDARY}; font-family: 'Segoe UI';"
            f"font-size: 10pt; font-weight: 500; background: transparent; }}"
        )
        self.title.text_changed.connect(self.title_changed.emit)
        layout.addWidget(self.title, 1)

        font_btn_style = f"""
            QPushButton {{
                background: transparent; color: {TEXT_MUTED};
                border: none; font-size: 8pt; font-weight: 600; padding: 0 3px;
            }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; }}
        """
        self.font_down_btn = QPushButton("A−")
        self.font_down_btn.setFixedSize(26, 22)
        self.font_down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.font_down_btn.setStyleSheet(font_btn_style)
        self.font_down_btn.clicked.connect(self.font_down_clicked.emit)
        self.font_down_btn.hide()
        layout.addWidget(self.font_down_btn)

        self.font_up_btn = QPushButton("A+")
        self.font_up_btn.setFixedSize(26, 22)
        self.font_up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.font_up_btn.setStyleSheet(font_btn_style)
        self.font_up_btn.clicked.connect(self.font_up_clicked.emit)
        self.font_up_btn.hide()
        layout.addWidget(self.font_up_btn)

        self.role_btn = QPushButton()
        self.role_btn.setIcon(get_icon("edit", color=TEXT_MUTED, size=14))
        self.role_btn.setIconSize(QSize(14, 14))
        self.role_btn.setFixedSize(22, 22)
        self.role_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.role_btn.setToolTip("Editar role gerenciado (.termicanvas/role.md)")
        self.role_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none; padding: 0;
            }}
            QPushButton:hover {{ background: {BG_ELEVATED}; border-radius: 2px; }}
        """)
        self.role_btn.clicked.connect(self.edit_role_clicked.emit)
        self.role_btn.hide()
        layout.addWidget(self.role_btn)

        self.auto_reply_btn = QPushButton()
        self.auto_reply_btn.setIconSize(QSize(14, 14))
        self.auto_reply_btn.setFixedSize(22, 22)
        self.auto_reply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_reply_btn.setCheckable(True)
        self.auto_reply_btn.setToolTip("Auto-responder: quando ativo, captura a resposta apos receber\nmensagem do bus e envia automaticamente ao emissor")
        self._update_auto_reply_btn_style()
        self.auto_reply_btn.toggled.connect(self._on_auto_reply_toggled)
        self.auto_reply_btn.hide()
        layout.addWidget(self.auto_reply_btn)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(16, 16)
        self.color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_btn.setToolTip("Cor da borda")
        self.color_btn.clicked.connect(self._pick_color)
        self.color_btn.hide()
        self._update_color_btn()
        layout.addWidget(self.color_btn)

        self.close_btn = QPushButton()
        self.close_btn.setIcon(get_icon("close", color=TEXT_SECONDARY, size=14))
        self.close_btn.setIconSize(QSize(14, 14))
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent;
                          border: none; padding: 0; }}
            QPushButton:hover {{ background: {DANGER}; border-radius: 2px; }}
        """)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.close_btn)

    def _on_icon_changed(self, text):
        # limita a 4 chars
        text = (text or "")[:4]
        if text != self.icon.text():
            self.icon.setText(text)
        self.icon.setFixedWidth(28 if text else 0)
        self.icon.setHidden(not text)
        self.icon_changed.emit(text)

    def set_icon(self, text):
        text = (text or "")[:4]
        self.icon.setText(text)
        self.icon.setFixedWidth(28 if text else 0)
        self.icon.setHidden(not text)

    def _update_color_btn(self):
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._accent_color};
                border: 1px solid {BORDER_HOVER};
                border-radius: 2px;
            }}
            QPushButton:hover {{ border-color: {TEXT_PRIMARY}; }}
        """)

    def _pick_color(self):
        # NodeHeader lives inside a QGraphicsProxyWidget — passing `self` as the
        # dialog parent makes Qt mis-position the modal and lose focus events.
        # Use the top-level application window instead.
        parent = QApplication.activeWindow()
        color = QColorDialog.getColor(QColor(self._accent_color), parent, "Cor da borda")
        if color.isValid():
            self._accent_color = color.name()
            self._update_color_btn()
            self.color_picked.emit(self._accent_color)

    def set_accent_color(self, color):
        self._accent_color = color
        self._update_color_btn()

    def show_font_controls(self):
        self.font_down_btn.show()
        self.font_up_btn.show()
        self.color_btn.show()

    def show_role_btn(self):
        self.role_btn.show()

    def show_auto_reply_btn(self):
        self.auto_reply_btn.show()

    def set_auto_reply_state(self, enabled):
        # Bloqueia signal pra nao re-emitir ao restaurar de session
        self.auto_reply_btn.blockSignals(True)
        self.auto_reply_btn.setChecked(bool(enabled))
        self.auto_reply_btn.blockSignals(False)
        self._update_auto_reply_btn_style()

    def _on_auto_reply_toggled(self, checked):
        self._update_auto_reply_btn_style()
        self.auto_reply_toggled.emit(checked)

    def _update_auto_reply_btn_style(self):
        on = self.auto_reply_btn.isChecked()
        bg     = SUCCESS if on else "transparent"
        icon_color = "white" if on else TEXT_MUTED
        self.auto_reply_btn.setIcon(get_icon("reply", color=icon_color, size=14))
        self.auto_reply_btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: none; border-radius: 2px;
                padding: 0;
            }}
            QPushButton:hover {{ background: {BG_ELEVATED}; }}
            QPushButton:checked {{ background: {SUCCESS}; }}
            QPushButton:checked:hover {{ background: {SUCCESS}; }}
        """)

    def _apply_style(self):
        self.setStyleSheet(f"""
            NodeHeader {{ background: {BG_ELEVATED};
                         border-bottom: 1px solid {BORDER};
                         border-top-left-radius: 6px;
                         border-top-right-radius: 6px; }}
        """)

    def set_focused(self, focused):
        """Foco visual no nó: título e dot indicador."""
        self._is_focused = bool(focused)
        # Titulo
        tcolor = TEXT_PRIMARY if focused else TEXT_SECONDARY
        self.title.set_label_style(
            f"QLabel {{ color: {tcolor}; font-family: 'Segoe UI';"
            f"font-size: 10pt; font-weight: 500; background: transparent; }}"
        )
        # Dot — verde glowing quando focado, azul muted quando nao
        self._refresh_dot()

    def _refresh_dot(self):
        if self._is_focused:
            # ativo: verde brilhante, fonte maior, bold (efeito glow)
            self.dot.setStyleSheet(
                f"color: {SUCCESS}; font-size: 11pt; font-weight: bold;"
                f" background: transparent;"
            )
        else:
            # idle: azul muted
            self.dot.setStyleSheet(
                "color: #3a5a8a; font-size: 9pt; background: transparent;"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging    = True
            self._last_global = QCursor.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.focus_requested.emit()
            QApplication.instance().installEventFilter(self)
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        if self._dragging:
            if event.type() == QEvent.Type.MouseMove:
                new_pos = QCursor.pos()
                delta   = QPointF(new_pos - self._last_global)
                self._last_global = new_pos
                if not delta.isNull():
                    self.drag_moved.emit(delta)
                return False
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._end_drag()
        return False

    def _end_drag(self):
        if self._dragging:
            self._dragging    = False
            self._last_global = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            QApplication.instance().removeEventFilter(self)

    def mouseReleaseEvent(self, event):
        self._end_drag()
        super().mouseReleaseEvent(event)


class ResizeGrip(QWidget):
    resize_moved = pyqtSignal(QPointF)

    def __init__(self):
        super().__init__()
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setStyleSheet("background: transparent;")
        self._last_pos = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(BORDER_HOVER), 1.3))
        for i in range(3):
            off = 5 + i * 4
            p.drawLine(off, 15, 15, off)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_pos = event.globalPosition()

    def mouseMoveEvent(self, event):
        if self._last_pos is not None:
            delta          = event.globalPosition() - self._last_pos
            self._last_pos = event.globalPosition()
            self.resize_moved.emit(delta)

    def mouseReleaseEvent(self, event):
        self._last_pos = None


class NodeFrame(QFrame):
    resized = pyqtSignal(QSize)

    def __init__(self, title, inner, icon=""):
        super().__init__()
        self.inner         = inner
        self._focused      = False
        self._node_color   = ACCENT
        self._custom_color = False
        self.setObjectName("node")
        self.setMinimumSize(260, 180)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.header = NodeHeader(title, icon=icon)
        main.addWidget(self.header)

        self.body = QWidget()
        self.body.setStyleSheet(f"QWidget {{ background: {BG_SURFACE}; }}")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(inner)
        main.addWidget(self.body, 1)

        self.grip = ResizeGrip()
        self.grip.setParent(self)
        self.grip.raise_()

        self._apply_style()

    def _apply_style(self):
        border = safe_border_color(self._node_color) if self._focused else BORDER
        width  = 2 if self._focused else 1
        self.setStyleSheet(f"""
            #node {{ background: {BG_SURFACE}; border: {width}px solid {border}; border-radius: 6px; }}
        """)

    def set_node_color(self, color, custom=False):
        self._node_color = color
        if custom:
            self._custom_color = True
        self.header.set_accent_color(color)
        self._apply_style()

    def set_focused(self, focused):
        if self._focused == focused:
            return
        self._focused = focused
        self._apply_style()
        self.header.set_focused(focused)

    def icon_text(self):
        return self.header.icon.text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grip.move(
            self.width()  - self.grip.width()  - 2,
            self.height() - self.grip.height() - 2,
        )
        self.resized.emit(event.size())

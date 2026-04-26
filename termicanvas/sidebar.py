"""TerminalsSidebar — lista vertical de terminais abertos (lateral esquerda).

Substitui o TerminalsBar horizontal que ficava na topbar. Usa o mesmo TerminalChip
adaptado para layout vertical.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .terminal import TerminalWidget
from .tokens import (
    ACCENT,
    BG_ELEVATED,
    BG_SIDEBAR,
    BORDER,
    BORDER_HOVER,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    safe_border_color,
)


class SidebarChip(QFrame):
    """Chip vertical para a sidebar — mais alto, full-width."""

    clicked = pyqtSignal()

    def __init__(self, frame):
        super().__init__()
        self.frame          = frame
        self._accent_color  = frame._node_color
        self._custom_accent = False
        self._is_focused    = False
        self.setObjectName("schip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(54)
        self._apply_style(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(8)

        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color: {SUCCESS}; font-size: 8pt; background: transparent;")
        layout.addWidget(self.dot)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self.name_label = QLabel(frame.header.title.text())
        self.name_label.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-family: 'Segoe UI';
            font-size: 9.5pt; font-weight: 500; background: transparent;
        """)
        self.name_label.setMaximumWidth(180)
        text_col.addWidget(self.name_label)

        self.cmd_label = QLabel("idle")
        self.cmd_label.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-family: 'Cascadia Mono','Consolas',monospace;
            font-size: 7.5pt; background: transparent;
        """)
        self.cmd_label.setMaximumWidth(180)
        text_col.addWidget(self.cmd_label)

        layout.addLayout(text_col, 1)

    def _apply_style(self, focused):
        border = safe_border_color(self._accent_color) if focused else BORDER
        bg     = BG_ELEVATED if focused else "transparent"
        self.setStyleSheet(f"""
            #schip {{ background: {bg}; border: 1px solid {border}; border-radius: 2px; }}
            #schip:hover {{ background: {BG_ELEVATED}; border-color: {BORDER_HOVER}; }}
        """)

    def set_accent(self, color, custom=False):
        self._accent_color = color
        if custom:
            self._custom_accent = True
        self._apply_style(self._is_focused)

    def set_focused(self, focused):
        self._is_focused = focused
        self._apply_style(focused)

    def set_activity(self, activity):
        if activity:
            self.dot.setStyleSheet(f"color: {ACCENT}; font-size: 8pt; background: transparent;")
            short = activity[:30] + ("…" if len(activity) > 30 else "")
            self.cmd_label.setText(f"▸ {short}")
            self.cmd_label.setStyleSheet(f"""
                color: {TEXT_SECONDARY}; font-family: 'Cascadia Mono','Consolas',monospace;
                font-size: 7.5pt; background: transparent;
            """)
        else:
            self.dot.setStyleSheet(f"color: {SUCCESS}; font-size: 8pt; background: transparent;")
            self.cmd_label.setText("idle")
            self.cmd_label.setStyleSheet(f"""
                color: {TEXT_MUTED}; font-family: 'Cascadia Mono','Consolas',monospace;
                font-size: 7.5pt; background: transparent;
            """)

    def set_title(self, title):
        self.name_label.setText(title)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class TerminalsSidebar(QWidget):
    """Sidebar vertical com lista de terminais. Substitui TerminalsBar horizontal."""

    terminal_clicked = pyqtSignal(object)
    collapse_toggled = pyqtSignal(bool)  # True = colapsado

    DEFAULT_WIDTH = 240

    def __init__(self):
        super().__init__()
        self.chips = {}
        self._collapsed = False
        self.setObjectName("sidebar")
        self.setFixedWidth(self.DEFAULT_WIDTH)
        self.setStyleSheet(f"""
            #sidebar {{
                background: {BG_SIDEBAR};
                border-right: 1px solid {BORDER};
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header com brand + collapse btn
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: transparent; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 8, 0)
        hl.setSpacing(8)

        brand = QLabel("TERMINAIS")
        brand.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; font-weight: 600;
            letter-spacing: 1.5px; background: transparent;
        """)
        hl.addWidget(brand, 1)

        outer.addWidget(header)

        # Lista scrollavel
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: {BORDER_HOVER}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._col = QVBoxLayout(self._inner)
        self._col.setContentsMargins(8, 10, 8, 10)
        self._col.setSpacing(6)
        self._col.addStretch()

        scroll.setWidget(self._inner)
        outer.addWidget(scroll, 1)

        # Empty-state label (visivel quando nao tem terminais)
        self._empty = QLabel("Nenhum terminal aberto.\nUse os botoes da topbar.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; background: transparent;
            padding: 20px;
        """)
        self._col.insertWidget(0, self._empty)

    def toggle(self):
        """Alterna colapsado/expandido. Pode ser chamado de fora (ex: botao na topbar)."""
        self._collapsed = not self._collapsed
        self.setFixedWidth(0 if self._collapsed else self.DEFAULT_WIDTH)
        self.collapse_toggled.emit(self._collapsed)

    def sync(self, canvas):
        terminals = [
            (proxy, f) for proxy, f in canvas.proxies
            if isinstance(f.inner, TerminalWidget)
        ]
        current_frames = {f for _, f in terminals}

        # Remove chips obsoletos
        for frame in list(self.chips.keys()):
            if frame not in current_frames:
                chip = self.chips.pop(frame)
                chip.setParent(None)
                chip.deleteLater()

        # Adiciona novos
        for _, frame in terminals:
            if frame not in self.chips:
                chip = SidebarChip(frame)
                chip.clicked.connect(lambda f=frame: self.terminal_clicked.emit(f))
                frame.inner.activity_changed.connect(
                    lambda act, c=chip: c.set_activity(act)
                )
                frame.header.title_changed.connect(
                    lambda t, c=chip: c.set_title(t)
                )
                frame.header.color_picked.connect(
                    lambda c, ch=chip: ch.set_accent(c, custom=True)
                )
                # insere antes do stretch (ultimo item)
                self._col.insertWidget(self._col.count() - 1, chip)
                self.chips[frame] = chip
                chip.set_activity(frame.inner.activity)

        # Atualiza foco
        for frame, chip in self.chips.items():
            chip.set_focused(frame is canvas.focused_frame)

        # Empty-state visibility
        self._empty.setVisible(len(self.chips) == 0)

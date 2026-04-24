"""TopBar + chips dos terminais ativos."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
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
    BG_SURFACE,
    BORDER,
    BORDER_HOVER,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class TerminalChip(QFrame):
    clicked = pyqtSignal()

    def __init__(self, frame):
        super().__init__()
        self.frame          = frame
        self._accent_color  = frame._node_color
        self._custom_accent = False
        self._is_focused    = False
        self.setObjectName("chip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(36)
        self.setMinimumWidth(110)
        self.setMaximumWidth(210)
        self._apply_style(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color: {SUCCESS}; font-size: 7pt; background: transparent;")
        layout.addWidget(self.dot)

        self.name_label = QLabel(frame.header.title.text())
        self.name_label.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-family: 'Segoe UI';
            font-size: 9pt; font-weight: 500; background: transparent;
        """)
        layout.addWidget(self.name_label, 1)

        self.cmd_label = QLabel("idle")
        self.cmd_label.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-family: 'Cascadia Mono','Consolas',monospace;
            font-size: 7.5pt; background: transparent;
        """)
        self.cmd_label.setMaximumWidth(80)
        layout.addWidget(self.cmd_label)

    def _apply_style(self, focused):
        border = self._accent_color if focused else BORDER
        bg     = BG_ELEVATED if focused else "transparent"
        self.setStyleSheet(f"""
            #chip {{ background: {bg}; border: 1px solid {border}; border-radius: 6px; }}
            #chip:hover {{ background: {BG_ELEVATED}; border-color: {BORDER_HOVER}; }}
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
            self.dot.setStyleSheet(f"color: {ACCENT}; font-size: 7pt; background: transparent;")
            short = activity[:18] + ("…" if len(activity) > 18 else "")
            self.cmd_label.setText(f"▸ {short}")
            self.cmd_label.setStyleSheet(f"""
                color: {TEXT_SECONDARY}; font-family: 'Cascadia Mono','Consolas',monospace;
                font-size: 7.5pt; background: transparent;
            """)
        else:
            self.dot.setStyleSheet(f"color: {SUCCESS}; font-size: 7pt; background: transparent;")
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


class TerminalsBar(QWidget):
    terminal_clicked = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: transparent;")
        self.chips = {}

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:horizontal {{
                background: transparent; height: 4px; margin: 0;
            }}
            QScrollBar::handle:horizontal {{
                background: {BORDER}; border-radius: 2px; min-width: 20px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        """)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._row = QHBoxLayout(self._inner)
        self._row.setContentsMargins(0, 6, 0, 6)
        self._row.setSpacing(6)
        self._row.addStretch()

        scroll.setWidget(self._inner)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(scroll)

    def sync(self, canvas):
        terminals = [
            (proxy, f) for proxy, f in canvas.proxies
            if isinstance(f.inner, TerminalWidget)
        ]
        current_frames = {f for _, f in terminals}

        for frame in list(self.chips.keys()):
            if frame not in current_frames:
                chip = self.chips.pop(frame)
                chip.setParent(None)
                chip.deleteLater()

        for _, frame in terminals:
            if frame not in self.chips:
                chip = TerminalChip(frame)
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
                self._row.insertWidget(self._row.count() - 1, chip)
                self.chips[frame] = chip
                chip.set_activity(frame.inner.activity)

        for frame, chip in self.chips.items():
            chip.set_focused(frame is canvas.focused_frame)


class TopBar(QWidget):
    add_terminal   = pyqtSignal(str)
    add_note       = pyqtSignal()
    add_agent      = pyqtSignal()
    add_prompt     = pyqtSignal()
    accent_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._accent_color = ACCENT
        self.setObjectName("topbar")
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            #topbar {{
                background: {BG_SIDEBAR};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        brand = QLabel("TERMICANVAS")
        brand.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-size: 11pt; font-weight: 600;
            letter-spacing: 2px; background: transparent;
        """)
        layout.addWidget(brand)

        layout.addSpacing(20)
        layout.addWidget(self._vline())
        layout.addSpacing(12)

        for label, slot in [
            ("PowerShell", lambda: self.add_terminal.emit("powershell.exe")),
            ("CMD",        lambda: self.add_terminal.emit("cmd.exe")),
            ("Nota",       self.add_note.emit),
            ("Prompt",     self.add_prompt.emit),
            ("Agent",      self.add_agent.emit),
        ]:
            b = self._add_btn(label)
            b.clicked.connect(slot)
            layout.addWidget(b)
            layout.addSpacing(4)

        layout.addSpacing(8)
        layout.addWidget(self._vline())
        layout.addSpacing(12)

        accent_lbl = QLabel("Cor ativa")
        accent_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8.5pt; background: transparent;")
        layout.addWidget(accent_lbl)
        layout.addSpacing(6)

        self._accent_swatch = QPushButton()
        self._accent_swatch.setFixedSize(20, 20)
        self._accent_swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self._accent_swatch.setToolTip("Mudar cor ativa global")
        self._accent_swatch.clicked.connect(self._pick_accent)
        self._update_swatch()
        layout.addWidget(self._accent_swatch)

        layout.addSpacing(12)
        layout.addWidget(self._vline())
        layout.addSpacing(12)

        self.terminals_bar = TerminalsBar()
        layout.addWidget(self.terminals_bar, 1)

    def _update_swatch(self):
        self._accent_swatch.setStyleSheet(f"""
            QPushButton {{
                background: {self._accent_color};
                border: 1px solid {BORDER_HOVER};
                border-radius: 10px;
            }}
            QPushButton:hover {{ border-color: {TEXT_PRIMARY}; }}
        """)

    def _pick_accent(self):
        color = QColorDialog.getColor(QColor(self._accent_color), self, "Cor ativa global")
        if color.isValid():
            self._accent_color = color.name()
            self._update_swatch()
            self.accent_changed.emit(self._accent_color)

    def _vline(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedSize(1, 24)
        sep.setStyleSheet(f"background: {BORDER}; border: none;")
        return sep

    def _add_btn(self, text):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedHeight(32)
        b.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SECONDARY};
                border: 1px solid {BORDER}; border-radius: 6px;
                padding: 0 12px; font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                border-color: {BORDER_HOVER};
            }}
            QPushButton:pressed {{ background: {BG_SURFACE}; }}
        """)
        return b

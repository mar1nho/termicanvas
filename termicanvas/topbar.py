"""TopBar — barra superior com brand, botoes de adicionar e accent picker.

A lista de terminais abertos esta em TerminalsSidebar (sidebar.py).
"""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from .icons import get_icon
from .tokens import (
    ACCENT,
    BG_ELEVATED,
    BG_SIDEBAR,
    BG_SURFACE,
    BORDER,
    BORDER_HOVER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class TopBar(QWidget):
    add_terminal       = pyqtSignal(str)
    add_agent_terminal = pyqtSignal(str)
    add_note           = pyqtSignal()
    add_agent          = pyqtSignal()
    add_prompt         = pyqtSignal()
    add_debug          = pyqtSignal()
    accent_changed     = pyqtSignal(str)
    toggle_sidebar     = pyqtSignal()

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
        layout.setContentsMargins(12, 0, 16, 0)
        layout.setSpacing(0)

        # toggle da sidebar (sempre visivel — nao some quando sidebar colapsa)
        self._sidebar_toggle = QPushButton()
        self._sidebar_toggle.setIcon(get_icon("menu", color=TEXT_SECONDARY, size=16))
        self._sidebar_toggle.setIconSize(QSize(16, 16))
        self._sidebar_toggle.setFixedSize(32, 32)
        self._sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sidebar_toggle.setToolTip("Mostrar/ocultar lista de terminais")
        self._sidebar_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {BORDER}; border-radius: 2px;
                padding: 0;
            }}
            QPushButton:hover {{
                border-color: {BORDER_HOVER};
                background: {BG_ELEVATED};
            }}
        """)
        self._sidebar_toggle.clicked.connect(self.toggle_sidebar.emit)
        layout.addWidget(self._sidebar_toggle)
        layout.addSpacing(12)

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
            ("Claude",     lambda: self.add_agent_terminal.emit("claude")),
            ("Gemini",     lambda: self.add_agent_terminal.emit("gemini")),
            ("Nota",       self.add_note.emit),
            ("Prompt",     self.add_prompt.emit),
            ("Agent",      self.add_agent.emit),
            ("Debug",      self.add_debug.emit),
        ]:
            b = self._add_btn(label)
            b.clicked.connect(slot)
            layout.addWidget(b)
            layout.addSpacing(4)

        layout.addStretch(1)

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

    def _update_swatch(self):
        self._accent_swatch.setStyleSheet(f"""
            QPushButton {{
                background: {self._accent_color};
                border: 1px solid {BORDER_HOVER};
                border-radius: 2px;
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

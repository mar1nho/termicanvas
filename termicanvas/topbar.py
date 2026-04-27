"""TopBar — barra superior com brand, botoes de adicionar e accent picker.

A lista de terminais abertos esta em TerminalsSidebar (sidebar.py).
"""

from PyQt6.QtCore import (
    QEasingCurve, QPropertyAnimation, QSize, Qt,
    pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter
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
    DANGER,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class BusToggleButton(QWidget):
    """Bolinha verde (ON) / vermelha pulsante (OFF) para o toggle do bus."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._state = True
        self._glow = 0.0

        self._anim = QPropertyAnimation(self, b"glow_intensity", self)
        self._anim.setDuration(3000)
        self._anim.setStartValue(0.0)
        self._anim.setKeyValueAt(0.5, 1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)

        self._refresh_tooltip()

    # -- glow animated property --
    def _get_glow(self):
        return self._glow

    def _set_glow(self, value):
        self._glow = float(value)
        self.update()

    glow_intensity = pyqtProperty(float, fget=_get_glow, fset=_set_glow)

    # -- public API --
    def set_state(self, enabled: bool):
        self._state = bool(enabled)
        self._refresh_tooltip()
        if self._state:
            self._anim.stop()
            self._glow = 0.0
        else:
            self._anim.start()
        self.update()

    # -- internals --
    def _refresh_tooltip(self):
        if self._state:
            self.setToolTip("Bus ligado · clique pra desligar")
        else:
            self.setToolTip("Bus desligado · clique pra ligar")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy, r = 12, 12, 7
        if self._state:
            color = QColor(SUCCESS)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
        else:
            base = QColor(DANGER)
            # outer ring (faint)
            outer = QColor(base)
            outer.setAlphaF(0.12 + 0.18 * self._glow)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outer)
            p.drawEllipse(cx - 12, cy - 12, 24, 24)
            # inner ring
            mid = QColor(base)
            mid.setAlphaF(0.30 + 0.30 * self._glow)
            p.setBrush(mid)
            p.drawEllipse(cx - 10, cy - 10, 20, 20)
            # solid core
            p.setBrush(base)
            p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
        p.end()


class TopBar(QWidget):
    add_terminal       = pyqtSignal(str)
    add_agent_terminal = pyqtSignal(str)
    add_note           = pyqtSignal()
    add_agent          = pyqtSignal()
    add_prompt         = pyqtSignal()
    add_debug          = pyqtSignal()
    accent_changed     = pyqtSignal(str)
    toggle_sidebar     = pyqtSignal()
    bus_toggled        = pyqtSignal(bool)

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

        self._bus_button = BusToggleButton()
        self._bus_button.clicked.connect(
            lambda: self.bus_toggled.emit(not self._bus_button._state)
        )
        layout.addWidget(self._bus_button)
        layout.addSpacing(8)

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

    def set_bus_state(self, enabled: bool):
        self._bus_button.set_state(enabled)

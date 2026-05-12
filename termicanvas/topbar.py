"""TopBar: bus toggle and accent picker."""

from PyQt6.QtCore import QByteArray, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QColorDialog, QHBoxLayout, QPushButton, QWidget

from .icons import get_icon
from .tokens import ACCENT, BG_ELEVATED, BORDER_HOVER, TEXT_PRIMARY, TEXT_SECONDARY


_BUS_OFF_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 496.158 496.158"><path style="fill:#EB9783;" d="M496.158,248.085c0-137.021-111.07-248.082-248.076-248.082C111.07,0.003,0,111.063,0,248.085 c0,137.002,111.07,248.07,248.082,248.07C385.088,496.155,496.158,385.087,496.158,248.085z"/><path style="fill:#D63232;" d="M373.299,154.891c-19.558-26.212-47.401-46.023-78.401-55.787c-0.759-0.238-1.588-0.103-2.229,0.369c-0.643,0.471-1.021,1.22-1.021,2.016l0.16,40.256c0,1.074,0.514,2.06,1.332,2.562c31.732,19.456,66.504,47,66.504,103.237c0,61.515-50.047,111.56-111.562,111.56c-61.517,0-111.566-50.045-111.566-111.56c0-58.737,35.199-84.661,67.615-103.917c0.836-0.496,1.363-1.492,1.363-2.58l0.154-39.909c0-0.793-0.375-1.539-1.013-2.01c-0.638-0.472-1.46-0.611-2.219-0.381c-31.283,9.586-59.41,29.357-79.202,55.672c-20.467,27.215-31.285,59.603-31.285,93.662c0,86.099,70.049,156.146,156.152,156.146c86.1,0,156.147-70.047,156.147-156.146C404.228,214.235,393.533,182.01,373.299,154.891z"/><path style="fill:#D63232;" d="M251.851,67.009h-7.549c-11.788,0-21.378,9.59-21.378,21.377v181.189c0,11.787,9.59,21.377,21.378,21.377h7.549c11.788,0,21.378-9.59,21.378-21.377V88.386C273.229,76.599,263.64,67.009,251.851,67.009z"/></svg>'''

_BUS_ON_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 496.158 496.158"><path style="fill:#89ec8f;" d="M496.158,248.085c0-137.021-111.07-248.082-248.076-248.082C111.07,0.003,0,111.063,0,248.085 c0,137.002,111.07,248.07,248.082,248.07C385.088,496.155,496.158,385.087,496.158,248.085z"/><path style="fill:#46d733;" d="M373.299,154.891c-19.558-26.212-47.401-46.023-78.401-55.787c-0.759-0.238-1.588-0.103-2.229,0.369c-0.643,0.471-1.021,1.22-1.021,2.016l0.16,40.256c0,1.074,0.514,2.06,1.332,2.562c31.732,19.456,66.504,47,66.504,103.237c0,61.515-50.047,111.56-111.562,111.56c-61.517,0-111.566-50.045-111.566-111.56c0-58.737,35.199-84.661,67.615-103.917c0.836-0.496,1.363-1.492,1.363-2.58l0.154-39.909c0-0.793-0.375-1.539-1.013-2.01c-0.638-0.472-1.46-0.611-2.219-0.381c-31.283,9.586-59.41,29.357-79.202,55.672c-20.467,27.215-31.285,59.603-31.285,93.662c0,86.099,70.049,156.146,156.152,156.146c86.1,0,156.147-70.047,156.147-156.146C404.228,214.235,393.533,182.01,373.299,154.891z"/><path style="fill:#46d733;" d="M251.851,67.009h-7.549c-11.788,0-21.378,9.59-21.378,21.377v181.189c0,11.787,9.59,21.377,21.378,21.377h7.549c11.788,0,21.378-9.59,21.378-21.377V88.386C273.229,76.599,263.64,67.009,251.851,67.009z"/></svg>'''


class BusToggleButton(QWidget):
    """SVG ON/OFF bus toggle."""

    clicked = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._state = True
        self._on_renderer = QSvgRenderer(QByteArray(_BUS_ON_SVG), self)
        self._off_renderer = QSvgRenderer(QByteArray(_BUS_OFF_SVG), self)

        self._refresh_tooltip()

    def set_state(self, enabled: bool):
        self._state = bool(enabled)
        self._refresh_tooltip()
        self.update()

    def _refresh_tooltip(self):
        if self._state:
            self.setToolTip("Bus ligado - clique pra desligar")
        else:
            self.setToolTip("Bus desligado - clique pra ligar")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(not self._state)
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer = self._on_renderer if self._state else self._off_renderer
        renderer.render(p, QRectF(self.rect()).adjusted(1, 1, -1, -1))
        p.end()


class TopBar(QWidget):
    accent_changed   = pyqtSignal(str)
    theme_toggled    = pyqtSignal(bool)   # True = light, False = dark
    bus_toggled      = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent_color = ACCENT
        self._light_mode   = False
        self.setObjectName("topbar")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(80, 28)
        self.setStyleSheet("#topbar { background: transparent; border: none; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)

        self._bus_button = BusToggleButton()
        self._bus_button.clicked.connect(self.bus_toggled.emit)
        layout.addWidget(self._bus_button)

        self._accent_swatch = QPushButton()
        self._accent_swatch.setFixedSize(16, 16)
        self._accent_swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self._accent_swatch.setToolTip("Cor de destaque global (borda dos nodes ativos)")
        self._accent_swatch.clicked.connect(self._pick_accent)
        self._update_accent_swatch()
        layout.addWidget(self._accent_swatch)

        # Botao de tema (sol/lua) — alterna fundo preto<->branco com grid invertido.
        self._theme_btn = QPushButton()
        self._theme_btn.setFixedSize(20, 20)
        self._theme_btn.setIconSize(QSize(14, 14))
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; padding: 0; }}
            QPushButton:hover {{ background: {BG_ELEVATED}; border-radius: 4px; }}
        """)
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._refresh_theme_btn()
        layout.addWidget(self._theme_btn)

    def _update_accent_swatch(self):
        self._accent_swatch.setStyleSheet(f"""
            QPushButton {{
                background: {self._accent_color};
                border: 1px solid {BORDER_HOVER};
                border-radius: 2px;
            }}
            QPushButton:hover {{ border-color: {TEXT_PRIMARY}; }}
        """)

    # Mantido por compat com main.py (alguns lugares chamam _update_swatch direto).
    _update_swatch = _update_accent_swatch

    def _refresh_theme_btn(self):
        # No modo dark mostra um sol (clique pra ir pra light); no light, lua.
        icon_name = "sun" if not self._light_mode else "moon"
        tooltip = "Alternar pra fundo claro" if not self._light_mode else "Alternar pra fundo escuro"
        self._theme_btn.setIcon(get_icon(icon_name, color=TEXT_SECONDARY, size=14))
        self._theme_btn.setToolTip(tooltip)

    def _toggle_theme(self):
        self._light_mode = not self._light_mode
        self._refresh_theme_btn()
        self.theme_toggled.emit(self._light_mode)

    def set_light_mode(self, enabled: bool):
        """Atualiza estado sem disparar signal (usado no restore da sessao)."""
        self._light_mode = bool(enabled)
        self._refresh_theme_btn()

    def _pick_accent(self):
        color = QColorDialog.getColor(QColor(self._accent_color), self, "Cor de destaque global")
        if color.isValid():
            self._accent_color = color.name()
            self._update_accent_swatch()
            self.accent_changed.emit(self._accent_color)

    def set_bus_state(self, enabled: bool):
        self._bus_button.set_state(enabled)

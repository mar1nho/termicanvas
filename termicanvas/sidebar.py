"""TerminalsSidebar — lista vertical de terminais abertos + secao de snapshots.

Layout:
- Top bar: toggle « pra recolher
- Section "TERMINAIS" colapsavel (chevron) com SidebarChip pra cada terminal
- Section "SNAPSHOTS" colapsavel (chevron + botao "+") com SnapshotChip
- Cantos direitos arredondados, adapta tema dark<->light via set_light_mode()
"""

from datetime import datetime

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPalette
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .icons import get_icon
from .terminal import TerminalWidget
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
    safe_border_color,
)


# Paletas dark/light usadas pelos componentes da sidebar. Mantidas locais para
# nao poluir os tokens globais (que descrevem o tema base do app, sempre dark).
_DARK_PALETTE = {
    "bg":             BG_SIDEBAR,
    "elevated":       BG_ELEVATED,
    "surface":        BG_SURFACE,
    "border":         BORDER,
    "border_hover":   BORDER_HOVER,
    "text_primary":   TEXT_PRIMARY,
    "text_secondary": TEXT_SECONDARY,
    "text_muted":     TEXT_MUTED,
    "hover":          "rgba(255, 255, 255, 0.04)",
    "section_hover":  "rgba(255, 255, 255, 0.03)",
}

_LIGHT_PALETTE = {
    "bg":             "#f5f5f5",
    "elevated":       "#e6e6e6",
    "surface":        "#ffffff",
    "border":         "#d4d4d4",
    "border_hover":   "#b0b0b0",
    "text_primary":   "#1a1a1a",
    "text_secondary": "#4a4a4a",
    "text_muted":     "#8a8a8a",
    "hover":          "rgba(0, 0, 0, 0.05)",
    "section_hover":  "rgba(0, 0, 0, 0.03)",
}


def _palette(light_mode: bool) -> dict:
    return _LIGHT_PALETTE if light_mode else _DARK_PALETTE


# Mapeamento tipo de widget interno -> nome do icone em icons.py.
# Resolvido em runtime via _icon_for_widget pra evitar imports circulares.
def _icon_for_widget(inner) -> str:
    """Retorna o nome do icone SVG correspondente ao tipo do widget interno."""
    # Imports locais pra nao ciclar com modulos que importam sidebar.
    from .agent import AgentWidget
    from .widgets import NoteWidget, PromptCard

    if isinstance(inner, TerminalWidget):
        kind = inner.agent_kind
        if kind == "claude":
            return "agent_claude"
        if kind == "gemini":
            return "agent_gemini"
        if kind == "codex":
            return "agent_openai"
        # PowerShell e CMD distinguem pelo shell binario.
        if (inner.shell or "").lower().startswith("cmd"):
            return "terminal_cmd"
        return "terminal_ps"
    if isinstance(inner, NoteWidget):
        return "edit"
    if isinstance(inner, PromptCard):
        return "clipboard"
    if isinstance(inner, AgentWidget):
        return "agent_code"
    # Debug Monitor importado tardiamente porque puxa psutil.
    try:
        from .monitor import DebugMonitorWidget
        if isinstance(inner, DebugMonitorWidget):
            return "bug"
    except Exception:
        pass
    return "box"


class SidebarChip(QFrame):
    """Chip vertical para a sidebar — mais alto, full-width."""

    clicked         = pyqtSignal()
    close_requested = pyqtSignal()
    move_up_requested = pyqtSignal()
    move_down_requested = pyqtSignal()

    def __init__(self, frame):
        super().__init__()
        self.frame         = frame
        self._accent_color = frame._node_color
        self._is_focused   = False
        self._light_mode   = False
        self._has_activity = False
        self.setObjectName("schip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(54)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(10)

        # Icone do tipo (PowerShell/CMD/Claude/Gemini/Note/Prompt/Agent/Debug)
        self._type_icon_name = _icon_for_widget(frame.inner)
        self.type_icon = QLabel()
        self.type_icon.setFixedSize(15, 15)
        self.type_icon.setStyleSheet("background: transparent;")
        layout.addWidget(self.type_icon)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        self.name_label = QLabel(frame.header.title.text())
        self.name_label.setMaximumWidth(150)
        text_col.addWidget(self.name_label)

        self.cmd_label = QLabel("idle")
        self.cmd_label.setMaximumWidth(150)
        text_col.addWidget(self.cmd_label)

        layout.addLayout(text_col, 1)
        # Dot de status (idle/active) — fica a direita, antes do close
        self.dot = QLabel("●")
        layout.addWidget(self.dot)

        self.up_btn = QPushButton()
        self.up_btn.setIconSize(QSize(10, 10))
        self.up_btn.setFixedSize(16, 16)
        self.up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.up_btn.clicked.connect(self.move_up_requested.emit)
        self.up_btn.mousePressEvent = self._up_btn_mouse_press
        layout.addWidget(self.up_btn)

        self.down_btn = QPushButton()
        self.down_btn.setIconSize(QSize(10, 10))
        self.down_btn.setFixedSize(16, 16)
        self.down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.down_btn.clicked.connect(self.move_down_requested.emit)
        self.down_btn.mousePressEvent = self._down_btn_mouse_press
        layout.addWidget(self.down_btn)

        self.close_btn = QPushButton()
        self.close_btn.setIconSize(QSize(11, 11))
        self.close_btn.setFixedSize(18, 18)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_requested.emit)
        # impede que o clique no X dispare o foco do chip (mousePressEvent do pai)
        self.close_btn.mousePressEvent = self._close_btn_mouse_press
        layout.addWidget(self.close_btn)

        self._apply_palette()

    def _close_btn_mouse_press(self, event):
        # consome o evento para nao propagar ao chip (que emitiria 'clicked')
        QPushButton.mousePressEvent(self.close_btn, event)
        event.accept()

    def _up_btn_mouse_press(self, event):
        QPushButton.mousePressEvent(self.up_btn, event)
        event.accept()

    def _down_btn_mouse_press(self, event):
        QPushButton.mousePressEvent(self.down_btn, event)
        event.accept()

    def _apply_palette(self):
        """Re-aplica todos os styles do chip conforme tema atual."""
        pal = _palette(self._light_mode)
        # Icones
        self.type_icon.setPixmap(
            get_icon(self._type_icon_name, color=pal["text_secondary"], size=15).pixmap(15, 15)
        )
        self.close_btn.setIcon(get_icon("close", color=pal["text_muted"], size=11))
        self.up_btn.setIcon(get_icon("chevron-left", color=pal["text_muted"], size=10))
        self.down_btn.setIcon(get_icon("chevron-right", color=pal["text_muted"], size=10))
        order_btn_style = f"""
            QPushButton {{ background: transparent; border: none; padding: 0; }}
            QPushButton:hover {{ background: {pal["elevated"]}; border-radius: 3px; }}
        """
        self.up_btn.setStyleSheet(order_btn_style)
        self.down_btn.setStyleSheet(order_btn_style)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; padding: 0; }}
            QPushButton:hover {{ background: {DANGER}; border-radius: 3px; }}
        """)
        # Texto
        self.name_label.setStyleSheet(f"""
            color: {pal["text_primary"]}; font-family: 'Segoe UI';
            font-size: 9.5pt; font-weight: 500; background: transparent;
        """)
        # Dot + cmd_label: dot vira branco em dark / preto em light pra
        # contraste maximo. Atividade ainda usa ACCENT.
        idle_dot = "#000000" if self._light_mode else "#ffffff"
        if self._has_activity:
            self.dot.setStyleSheet(f"color: {ACCENT}; font-size: 7pt; background: transparent;")
            self.cmd_label.setStyleSheet(f"""
                color: {pal["text_secondary"]}; font-family: 'Cascadia Mono','Consolas',monospace;
                font-size: 7.5pt; background: transparent;
            """)
        else:
            self.dot.setStyleSheet(f"color: {idle_dot}; font-size: 7pt; background: transparent;")
            self.cmd_label.setStyleSheet(f"""
                color: {pal["text_muted"]}; font-family: 'Cascadia Mono','Consolas',monospace;
                font-size: 7.5pt; background: transparent;
            """)
        # Background do chip (focused ou nao)
        self._apply_style(self._is_focused)

    def apply_theme(self, light_mode: bool):
        self._light_mode = bool(light_mode)
        self._apply_palette()

    def _apply_style(self, focused):
        # Item focado: fundo elevado + barra esquerda accent (3px) discreta.
        # Hover: so muda o fundo, sem alterar borda (evita "salto" visual).
        pal = _palette(self._light_mode)
        if focused:
            self.setStyleSheet(f"""
                #schip {{
                    background: {pal["elevated"]};
                    border: none;
                    border-left: 3px solid {safe_border_color(self._accent_color)};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                #schip {{
                    background: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 6px;
                }}
                #schip:hover {{ background: {pal["hover"]}; }}
            """)

    def set_accent(self, color):
        self._accent_color = color
        self._apply_style(self._is_focused)

    def set_focused(self, focused):
        self._is_focused = focused
        self._apply_style(focused)

    def set_activity(self, activity):
        if activity:
            self._has_activity = True
            short = activity[:30] + ("…" if len(activity) > 30 else "")
            self.cmd_label.setText(f"▸ {short}")
        else:
            self._has_activity = False
            self.cmd_label.setText("idle")
        # Re-aplica styles porque dot/cmd_label dependem de _has_activity
        self._apply_palette()

    def set_subtitle(self, text):
        self._has_activity = False
        self.cmd_label.setText(text)
        self._apply_palette()

    def set_title(self, title):
        self.name_label.setText(title)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class SnapshotChip(QFrame):
    """Chip de snapshot na sidebar.

    Layout: nome + badge "N nodes" + ⋮ menu (rename / overwrite / delete).
    Clique no chip emite load_requested.
    """

    load_requested      = pyqtSignal(str)   # file_name
    rename_requested    = pyqtSignal(str)   # file_name
    overwrite_requested = pyqtSignal(str)   # file_name
    delete_requested    = pyqtSignal(str)   # file_name

    def __init__(self, info: dict):
        super().__init__()
        self.file_name = info["file_name"]
        self._light_mode = False
        self.setObjectName("snapchip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(56)
        # Expande horizontal pra preencher a coluna da sidebar — sem isso o
        # chip fica com size hint < largura disponivel e o ⋮ acaba flutuando
        # no meio (parecendo "cortado" em DPI > 100%).
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(8)

        # Icone de snapshot
        self.icon = QLabel()
        self.icon.setFixedSize(15, 15)
        self.icon.setStyleSheet("background: transparent;")
        layout.addWidget(self.icon)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        # Nome e meta usam minimumWidth=0 + sizePolicy Ignored pra deixar a
        # coluna controlar a largura — labels longos elidam via paintEvent.
        self.name_label = QLabel(info["name"])
        self.name_label.setMinimumWidth(0)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._name_full = info["name"]
        text_col.addWidget(self.name_label)

        node_count = info.get("node_count", 0)
        modified_at = info.get("modified_at", 0)
        when = datetime.fromtimestamp(modified_at).strftime("%d/%m %H:%M") if modified_at else "?"
        meta_text = f"{node_count} node{'s' if node_count != 1 else ''} · {when}"
        self.meta_label = QLabel(meta_text)
        self.meta_label.setMinimumWidth(0)
        self.meta_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._meta_full = meta_text
        text_col.addWidget(self.meta_label)

        layout.addLayout(text_col, 1)

        self.menu_btn = QPushButton("⋮")
        self.menu_btn.setFixedSize(22, 22)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.clicked.connect(self._show_menu)
        # consome o clique para nao propagar pra mousePressEvent do chip
        self.menu_btn.mousePressEvent = self._menu_btn_mouse_press
        layout.addWidget(self.menu_btn)

        self._apply_palette()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide_labels()

    def _elide_labels(self):
        fm = self.name_label.fontMetrics()
        avail = max(0, self.name_label.width())
        self.name_label.setText(fm.elidedText(self._name_full, Qt.TextElideMode.ElideRight, avail))
        fm2 = self.meta_label.fontMetrics()
        avail2 = max(0, self.meta_label.width())
        self.meta_label.setText(fm2.elidedText(self._meta_full, Qt.TextElideMode.ElideRight, avail2))

    def _apply_palette(self):
        pal = _palette(self._light_mode)
        self.setStyleSheet(f"""
            #snapchip {{
                background: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 6px;
            }}
            #snapchip:hover {{ background: {pal["hover"]}; }}
        """)
        self.icon.setPixmap(
            get_icon("save", color=pal["text_secondary"], size=15).pixmap(15, 15)
        )
        self.name_label.setStyleSheet(f"""
            color: {pal["text_primary"]}; font-family: 'Segoe UI';
            font-size: 9.5pt; font-weight: 500; background: transparent;
        """)
        self.meta_label.setStyleSheet(f"""
            color: {pal["text_muted"]}; font-family: 'Segoe UI';
            font-size: 7.5pt; background: transparent;
        """)
        self.menu_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {pal["text_secondary"]};
                border: none; padding: 0; font-size: 13pt;
            }}
            QPushButton:hover {{ background: {pal["elevated"]}; border-radius: 2px;
                                color: {pal["text_primary"]}; }}
        """)

    def apply_theme(self, light_mode: bool):
        self._light_mode = bool(light_mode)
        self._apply_palette()

    def _menu_btn_mouse_press(self, event):
        QPushButton.mousePressEvent(self.menu_btn, event)
        event.accept()

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                    border: 1px solid {BORDER}; padding: 4px; }}
            QMenu::item {{ padding: 6px 14px; border-radius: 3px; }}
            QMenu::item:selected {{ background: {ACCENT}; color: white; }}
        """)
        rename_act    = menu.addAction("Renomear")
        overwrite_act = menu.addAction("Sobrescrever com canvas atual")
        menu.addSeparator()
        delete_act    = menu.addAction("Deletar")

        action = menu.exec(self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft()))
        if action is rename_act:
            self.rename_requested.emit(self.file_name)
        elif action is overwrite_act:
            self.overwrite_requested.emit(self.file_name)
        elif action is delete_act:
            self.delete_requested.emit(self.file_name)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.load_requested.emit(self.file_name)


class SectionHeader(QWidget):
    """Header colapsavel de uma secao da sidebar.

    Mostra chevron-down/chevron-right + label em caps. Opcionalmente um
    botao extra a direita (usado pelo SNAPSHOTS pra criar snapshot novo).
    Click no header inteiro alterna o estado expandido <-> colapsado e
    emite toggled(bool).
    """

    toggled = pyqtSignal(bool)  # True = expandido, False = colapsado

    def __init__(self, label: str, extra_button: QPushButton = None):
        super().__init__()
        self.setObjectName("sectionhdr")
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expanded = True
        self._light_mode = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(8)

        self.chevron = QLabel()
        self.chevron.setFixedSize(10, 10)
        self.chevron.setStyleSheet("background: transparent;")
        layout.addWidget(self.chevron)

        self.label = QLabel(label)
        layout.addWidget(self.label, 1)

        self._apply_palette()

        if extra_button is not None:
            layout.addWidget(extra_button)
            # Bota o botao extra fora do clique do header (pra nao toggle
            # quando o user clica nele).
            extra_button.installEventFilter(self)

    def _apply_palette(self):
        pal = _palette(self._light_mode)
        self.setStyleSheet(f"""
            #sectionhdr {{ background: transparent; border-radius: 4px; }}
            #sectionhdr:hover {{ background: {pal["section_hover"]}; }}
        """)
        self.label.setStyleSheet(f"""
            color: {pal["text_muted"]}; font-size: 7.5pt; font-weight: 700;
            letter-spacing: 2px; background: transparent;
        """)
        self._refresh_chevron()

    def apply_theme(self, light_mode: bool):
        self._light_mode = bool(light_mode)
        self._apply_palette()

    def _refresh_chevron(self):
        pal = _palette(self._light_mode)
        name = "chevron-down" if self._expanded else "chevron-right"
        self.chevron.setPixmap(get_icon(name, color=pal["text_muted"], size=10).pixmap(10, 10))

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool):
        self._expanded = bool(expanded)
        self._refresh_chevron()

    def eventFilter(self, obj, event):
        # Bloqueia toggle quando o clique foi no botao extra (ex: o "+" do snapshots).
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress:
            return False
        return False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Verifica se o clique foi sobre o extra button (filho do header) —
            # se sim, deixa o botao tratar; senao, faz toggle.
            for child in self.children():
                if isinstance(child, QPushButton) and child.underMouse():
                    return
            self._expanded = not self._expanded
            self._refresh_chevron()
            self.toggled.emit(self._expanded)
        super().mousePressEvent(event)


class TerminalsSidebar(QWidget):
    """Sidebar vertical com lista de terminais e snapshots."""

    terminal_clicked = pyqtSignal(object)
    collapse_toggled = pyqtSignal(bool)

    snapshot_save_requested      = pyqtSignal()        # botao "+" header
    snapshot_load_requested      = pyqtSignal(str)
    snapshot_rename_requested    = pyqtSignal(str)
    snapshot_overwrite_requested = pyqtSignal(str)
    snapshot_delete_requested    = pyqtSignal(str)

    DEFAULT_WIDTH = 248
    COLLAPSED_WIDTH = 44

    def __init__(self):
        super().__init__()
        self.chips = {}
        self._snap_chips = []
        self._collapsed = False
        self._light_mode = False
        self.setObjectName("sidebar")
        self.setFixedWidth(self.DEFAULT_WIDTH)
        self._apply_root_style()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Top bar: 3 dots decorativos + spacer + toggle «
        outer.addWidget(self._make_top_bar())

        # Lista scrollavel — duas secoes (terminais + snapshots) numa unica scroll area
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: {BORDER_HOVER}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._col = QVBoxLayout(self._inner)
        self._col.setContentsMargins(6, 8, 6, 10)
        self._col.setSpacing(4)

        # Section AGENTES (colapsavel)
        self._agent_header = SectionHeader("AGENTES")
        self._agent_header.toggled.connect(self._on_agents_toggled)
        self._col.addWidget(self._agent_header)

        self._agent_empty = QLabel("Nenhum agente aberto.")
        self._agent_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._agent_empty.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; background: transparent;
            padding: 14px 12px;
        """)
        self._col.addWidget(self._agent_empty)

        self._col.addSpacing(8)

        # Section TERMINAIS (colapsavel)
        self._term_header = SectionHeader("TERMINAIS")
        self._term_header.toggled.connect(self._on_terminals_toggled)
        self._col.addWidget(self._term_header)

        # Empty-state label dos terminais
        self._empty = QLabel("Nenhum terminal puro aberto.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; background: transparent;
            padding: 14px 12px;
        """)
        self._col.addWidget(self._empty)

        self._col.addSpacing(8)

        # Section WIDGETS (notas, prompts, previews, etc.)
        self._widget_header = SectionHeader("WIDGETS")
        self._widget_header.toggled.connect(self._on_widgets_toggled)
        self._col.addWidget(self._widget_header)

        self._widget_empty = QLabel("Nenhuma nota/widget aberto.")
        self._widget_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._widget_empty.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; background: transparent;
            padding: 14px 12px;
        """)
        self._col.addWidget(self._widget_empty)

        # Section SNAPSHOTS (colapsavel + botao de salvar visivel)
        self._save_btn = QPushButton("Salvar snapshot")
        self._save_btn.setIcon(get_icon("save", color=TEXT_SECONDARY, size=13))
        self._save_btn.setIconSize(QSize(13, 13))
        self._save_btn.setFixedHeight(28)
        self._save_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setToolTip("Salvar canvas atual como snapshot (Ctrl+S)")
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SECONDARY};
                border: 1px solid {BORDER}; border-radius: 5px;
                font-size: 8.5pt; font-weight: 600;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                border-color: {BORDER_HOVER};
            }}
        """)
        self._save_btn.clicked.connect(self.snapshot_save_requested.emit)

        self._snap_header = SectionHeader("SNAPSHOTS")
        self._snap_header.toggled.connect(self._on_snapshots_toggled)
        # Spacer pra dar respiro entre TERMINAIS e SNAPSHOTS (sem linha dura).
        self._col.addSpacing(12)
        self._col.addWidget(self._snap_header)
        self._col.addWidget(self._save_btn)

        # Empty-state dos snapshots
        self._snap_empty = QLabel("Nenhum snapshot.\nClique '+' pra salvar o canvas atual.")
        self._snap_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._snap_empty.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; background: transparent;
            padding: 16px 12px;
        """)
        self._col.addWidget(self._snap_empty)

        self._col.addStretch()

        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

        # Re-aplica a paleta agora que _inner e _scroll existem — a primeira
        # chamada de _apply_root_style passou batido neles (criados depois).
        self._apply_root_style()

    def _make_top_bar(self) -> QWidget:
        """Top bar minimalista: so o toggle alinhado a direita."""
        self._top_bar = QWidget()
        header = self._top_bar
        header.setFixedHeight(40)
        header.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 8, 0)
        hl.setSpacing(0)

        hl.addStretch()

        self._toggle_btn = QPushButton()
        self._toggle_btn.setIcon(get_icon("menu", color=TEXT_SECONDARY, size=18))
        self._toggle_btn.setIconSize(QSize(18, 18))
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setToolTip("Mostrar/ocultar lista de terminais")
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; padding: 0;
            }}
            QPushButton:hover {{
                background: {BG_ELEVATED}; border-radius: 6px;
            }}
        """)
        self._toggle_btn.clicked.connect(self.toggle)
        hl.addWidget(self._toggle_btn)
        return header

    def toggle(self):
        """Alterna colapsado/expandido mantendo o botao preso na sidebar."""
        self._collapsed = not self._collapsed
        self.setFixedWidth(self.COLLAPSED_WIDTH if self._collapsed else self.DEFAULT_WIDTH)
        self._scroll.setVisible(not self._collapsed)
        # Esconde explicitamente cada widget interno — setVisible no parent
        # nao tava propagando 100% (chip close_btns ficavam visiveis ainda na
        # sidebar de 44px com nome cortado).
        visible = not self._collapsed
        self._agent_header.setVisible(visible)
        self._term_header.setVisible(visible)
        self._widget_header.setVisible(visible)
        self._snap_header.setVisible(visible)
        self._agent_empty.setVisible(visible and self._agent_header.is_expanded() and self._count_category("agent") == 0)
        self._empty.setVisible(visible and self._term_header.is_expanded() and self._count_category("terminal") == 0)
        self._widget_empty.setVisible(visible and self._widget_header.is_expanded() and self._count_category("widget") == 0)
        self._save_btn.setVisible(visible and self._snap_header.is_expanded())
        self._snap_empty.setVisible(visible and self._snap_header.is_expanded() and len(self._snap_chips) == 0)
        for chip in self.chips.values():
            chip.setVisible(visible and self._header_for_frame(chip.frame).is_expanded())
        for chip in self._snap_chips:
            chip.setVisible(visible and self._snap_header.is_expanded())
        self.collapse_toggled.emit(self._collapsed)

    # ---------- tema (dark/light) ----------

    def paintEvent(self, event):
        """Pinta o bg da sidebar diretamente via QPainter — bypass de stylesheet
        e palette do Qt, que estavam falhando em areas vazias (sidebar
        colapsada, regiao apos o ultimo widget). Cantos arredondados nos lados
        direitos sao aplicados via clipping path."""
        pal = _palette(self._light_mode)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        # Radius so nos cantos direitos — esquerdo cola na borda da janela.
        # Truque: desenhamos um retangulo estendido pra esquerda 12px alem do
        # widget, com cantos arredondados de 12px; a parte que sai e cortada
        # pela janela, deixando so os cantos direitos visiveis arredondados.
        r = self.rect()
        path.addRoundedRect(
            r.x() - 12, r.y(), r.width() + 12, r.height(), 12, 12,
        )
        p.fillPath(path, QColor(pal["bg"]))
        p.end()
        super().paintEvent(event)

    def _apply_root_style(self):
        pal = _palette(self._light_mode)
        bg = pal["bg"]

        # Setamos bg em CADA widget interno explicitamente. Stylesheets do Qt
        # nao herdam pra children, e o #sidebar so estiliza o widget root.
        # Sem isso o _inner e o viewport do scroll continuam com o cinza
        # padrao do sistema, ignorando o tema.
        self.setStyleSheet(f"""
            #sidebar {{
                background: {bg};
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }}
        """)

        if hasattr(self, "_inner") and self._inner is not None:
            self._inner.setStyleSheet(f"background: {bg};")
        if hasattr(self, "_scroll") and self._scroll is not None:
            self._scroll.viewport().setStyleSheet(f"background: {bg};")
        if hasattr(self, "_top_bar") and self._top_bar is not None:
            self._top_bar.setStyleSheet(f"background: {bg};")

        # QPalette como reforco (autoFillBackground pra widgets sem stylesheet).
        bg_color = QColor(bg)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, bg_color)
        palette.setColor(QPalette.ColorRole.Base,   bg_color)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        # Forca Qt a re-renderizar o stylesheet imediatamente.
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_light_mode(self, enabled: bool):
        """Adapta toda a sidebar ao tema (dark/light). Propaga pros children
        (top bar, section headers, chips, snap chips, empty states)."""
        self._light_mode = bool(enabled)
        pal = _palette(self._light_mode)
        self._apply_root_style()
        # Top bar toggle button — refaz icon na cor do tema
        self._toggle_btn.setIcon(get_icon("menu", color=pal["text_secondary"], size=18))
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; padding: 0; }}
            QPushButton:hover {{ background: {pal["elevated"]}; border-radius: 6px; }}
        """)
        # Section headers
        self._agent_header.apply_theme(self._light_mode)
        self._term_header.apply_theme(self._light_mode)
        self._widget_header.apply_theme(self._light_mode)
        self._snap_header.apply_theme(self._light_mode)
        # Save button (+) dentro do snap header
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {pal["text_secondary"]};
                border: 1px solid {pal["border"]}; border-radius: 5px;
                font-size: 8.5pt; font-weight: 600;
            }}
            QPushButton:hover {{
                background: {pal["elevated"]}; color: {pal["text_primary"]};
                border-color: {pal["border_hover"]};
            }}
        """)
        self._save_btn.setIcon(get_icon("save", color=pal["text_secondary"], size=13))
        # Scroll area scrollbar
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {pal["border"]}; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: {pal["border_hover"]}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        # Empty states
        empty_style = f"""
            color: {pal["text_muted"]}; font-size: 8.5pt; background: transparent;
            padding: 20px;
        """
        self._empty.setStyleSheet(empty_style)
        self._agent_empty.setStyleSheet(empty_style.replace("padding: 20px", "padding: 14px 12px"))
        self._widget_empty.setStyleSheet(empty_style.replace("padding: 20px", "padding: 14px 12px"))
        self._snap_empty.setStyleSheet(empty_style.replace("padding: 20px", "padding: 16px 12px"))
        # Chips (terminais + snapshots)
        for chip in self.chips.values():
            chip.apply_theme(self._light_mode)
        for chip in self._snap_chips:
            chip.apply_theme(self._light_mode)
        # Forca repaint da arvore inteira (incluindo scroll area e children).
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    # ---------- expand/collapse das secoes ----------

    def _on_agents_toggled(self, expanded: bool):
        for frame, chip in self.chips.items():
            if self._category_for_frame(frame) == "agent":
                chip.setVisible(expanded)
        self._agent_empty.setVisible(expanded and self._count_category("agent") == 0)

    def _on_terminals_toggled(self, expanded: bool):
        # Mostra/esconde todos os SidebarChip + o empty-state de terminais.
        for frame, chip in self.chips.items():
            if self._category_for_frame(frame) == "terminal":
                chip.setVisible(expanded)
        self._empty.setVisible(expanded and self._count_category("terminal") == 0)

    def _on_widgets_toggled(self, expanded: bool):
        for frame, chip in self.chips.items():
            if self._category_for_frame(frame) == "widget":
                chip.setVisible(expanded)
        self._widget_empty.setVisible(expanded and self._count_category("widget") == 0)

    def _on_snapshots_toggled(self, expanded: bool):
        # Mostra/esconde todos os SnapshotChip + o empty-state de snapshots.
        self._save_btn.setVisible(expanded)
        for chip in self._snap_chips:
            chip.setVisible(expanded)
        self._snap_empty.setVisible(expanded and len(self._snap_chips) == 0)

    # ---------- API publica ----------

    def _category_for_frame(self, frame):
        if isinstance(frame.inner, TerminalWidget):
            return "agent" if frame.inner.agent_kind else "terminal"
        return "widget"

    def _header_for_frame(self, frame):
        category = self._category_for_frame(frame)
        if category == "agent":
            return self._agent_header
        if category == "terminal":
            return self._term_header
        return self._widget_header

    def _count_category(self, category):
        return sum(1 for frame in self.chips if self._category_for_frame(frame) == category)

    def _empty_label_for_category(self, category):
        if category == "agent":
            return self._agent_empty
        if category == "terminal":
            return self._empty
        return self._widget_empty

    def _subtitle_for_frame(self, frame):
        if isinstance(frame.inner, TerminalWidget):
            return frame.inner.activity or "idle"
        name = frame.inner.__class__.__name__.replace("Widget", "")
        if name == "PromptCard":
            return "prompt"
        if name == "Preview":
            return "preview"
        if name == "Note":
            return "nota"
        return name.lower()

    def sync(self, canvas):
        frames = [(proxy, f) for proxy, f in canvas.proxies]
        current_frames = {f for _, f in frames}

        # Remove chips obsoletos
        for frame in list(self.chips.keys()):
            if frame not in current_frames:
                chip = self.chips.pop(frame)
                chip.setParent(None)
                chip.deleteLater()

        for _, frame in frames:
            if frame not in self.chips:
                chip = SidebarChip(frame)
                chip.clicked.connect(lambda f=frame: self.terminal_clicked.emit(f))
                chip.close_requested.connect(lambda f=frame: canvas._close(f))
                chip.move_up_requested.connect(lambda f=frame: canvas.move_frame_in_order(f, -1))
                chip.move_down_requested.connect(lambda f=frame: canvas.move_frame_in_order(f, 1))
                if isinstance(frame.inner, TerminalWidget):
                    frame.inner.activity_changed.connect(
                        lambda act, c=chip: c.set_activity(act)
                    )
                frame.header.title_changed.connect(
                    lambda t, c=chip: c.set_title(t)
                )
                # Respeita o estado colapsado da secao e o tema atual.
                chip.setVisible(self._header_for_frame(frame).is_expanded())
                chip.apply_theme(self._light_mode)
                self.chips[frame] = chip
                if isinstance(frame.inner, TerminalWidget):
                    chip.set_activity(frame.inner.activity)
                else:
                    chip.set_subtitle(self._subtitle_for_frame(frame))

        # Atualiza foco
        for chip in self.chips.values():
            self._col.removeWidget(chip)

        for category in ("agent", "terminal", "widget"):
            for _, frame in frames:
                if frame in self.chips and self._category_for_frame(frame) == category:
                    chip = self.chips[frame]
                    insert_at = self._col.indexOf(self._empty_label_for_category(category))
                    self._col.insertWidget(insert_at, chip)
                    chip.setVisible(self._header_for_frame(frame).is_expanded())

        for frame, chip in self.chips.items():
            chip.set_focused(frame is canvas.focused_frame)

        # Empty-state visibility — so aparece se a secao estiver expandida
        self._agent_empty.setVisible(
            self._agent_header.is_expanded() and self._count_category("agent") == 0
        )
        self._empty.setVisible(
            self._term_header.is_expanded() and self._count_category("terminal") == 0
        )
        self._widget_empty.setVisible(
            self._widget_header.is_expanded() and self._count_category("widget") == 0
        )

    def set_snapshots(self, snapshots: list):
        """Re-renderiza a lista de snapshot chips. Chamado depois de save/delete/rename."""
        # Limpa chips existentes
        for chip in self._snap_chips:
            chip.setParent(None)
            chip.deleteLater()
        self._snap_chips = []

        # Insere depois do snap_empty (antes do stretch).
        insert_at = self._col.indexOf(self._snap_empty) + 1

        for info in snapshots:
            chip = SnapshotChip(info)
            chip.load_requested.connect(self.snapshot_load_requested.emit)
            chip.rename_requested.connect(self.snapshot_rename_requested.emit)
            chip.overwrite_requested.connect(self.snapshot_overwrite_requested.emit)
            chip.delete_requested.connect(self.snapshot_delete_requested.emit)
            # Respeita o estado colapsado da secao e o tema atual.
            chip.setVisible(self._snap_header.is_expanded())
            chip.apply_theme(self._light_mode)
            self._col.insertWidget(insert_at, chip)
            insert_at += 1
            self._snap_chips.append(chip)

        self._snap_empty.setVisible(
            self._snap_header.is_expanded() and len(snapshots) == 0
        )

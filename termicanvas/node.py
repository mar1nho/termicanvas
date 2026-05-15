"""NodeHeader, ResizeGrip, NodeFrame: chrome dos cards no canvas."""

from PyQt6.QtCore import QEvent, QPointF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import get_icon


def _icon_for_inner(inner) -> str:
    """Mapeia o widget interno -> nome do icone SVG em icons.py.
    Mesma logica do _icon_for_widget da sidebar, duplicada aqui pra evitar
    import circular sidebar <-> node."""
    # Imports locais pra nao ciclar.
    from .agent import AgentWidget
    from .preview import PreviewWidget
    from .terminal import TerminalWidget
    from .widgets import NoteWidget, PromptCard

    if isinstance(inner, TerminalWidget):
        kind = inner.agent_kind
        if kind == "claude":
            return "agent_claude"
        if kind == "gemini":
            return "agent_gemini"
        if kind == "codex":
            return "agent_openai"
        if (inner.shell or "").lower().startswith("cmd"):
            return "terminal_cmd"
        return "terminal_ps"
    if isinstance(inner, NoteWidget):
        return "edit"
    if isinstance(inner, PromptCard):
        return "clipboard"
    if isinstance(inner, AgentWidget):
        return "agent_code"
    if isinstance(inner, PreviewWidget):
        return "monitor"
    try:
        from .monitor import DebugMonitorWidget
        if isinstance(inner, DebugMonitorWidget):
            return "bug"
    except Exception:
        pass
    return "box"
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
    drag_finished   = pyqtSignal()
    close_clicked   = pyqtSignal()
    focus_requested = pyqtSignal()
    title_changed   = pyqtSignal(str)
    icon_changed    = pyqtSignal(str)
    font_up_clicked   = pyqtSignal()
    font_down_clicked = pyqtSignal()
    edit_role_clicked  = pyqtSignal()
    inbox_clicked      = pyqtSignal()
    chain_clicked      = pyqtSignal()
    purge_clicked      = pyqtSignal()
    compact_clicked    = pyqtSignal()

    def __init__(self, title, icon=""):
        super().__init__()
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._dragging     = False
        self._last_global  = None
        self._is_focused   = False  # alimenta o indicador idle/ativo
        self._light_mode   = False
        self._is_compacted  = False
        self._apply_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(10)

        self.dot = QLabel("●")
        layout.addWidget(self.dot)
        self._refresh_dot()

        # Icone do tipo (SVG) — preenchido depois via set_type_icon pelo NodeFrame.
        # Comeca oculto; se nao houver tipo conhecido, fica zero-width.
        self._type_icon_name = ""
        self.icon = QLabel()
        self.icon.setFixedSize(18, 18)
        self.icon.setStyleSheet("background: transparent;")
        self.icon.setHidden(True)
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

        self.inbox_btn = QPushButton("📥 0")
        self.inbox_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.inbox_btn.setToolTip(
            "Mensagens pendentes no inbox.\n"
            "Clique pra cutucar o terminal a rodar `inbox` (so o comando).\n"
            "Bus tambem cutuca automaticamente em terminais idle."
        )
        self._update_inbox_btn_style(0)
        self.inbox_btn.clicked.connect(self.inbox_clicked.emit)
        self.inbox_btn.hide()
        layout.addWidget(self.inbox_btn)

        self.chain_btn = QPushButton()
        self.chain_btn.setIcon(get_icon("link", color=TEXT_MUTED, size=14))
        self.chain_btn.setIconSize(QSize(14, 14))
        self.chain_btn.setFixedSize(22, 22)
        self.chain_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chain_btn.setToolTip("Linkar uma corrente a outro terminal — clique aqui, depois no alvo")
        self.chain_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none; padding: 0;
            }}
            QPushButton:hover {{ background: {BG_ELEVATED}; border-radius: 2px; }}
        """)
        self.chain_btn.clicked.connect(self.chain_clicked.emit)
        self.chain_btn.hide()
        layout.addWidget(self.chain_btn)

        self.purge_btn = QPushButton()
        self.purge_btn.setIcon(get_icon("trash", color=TEXT_MUTED, size=14))
        self.purge_btn.setIconSize(QSize(14, 14))
        self.purge_btn.setFixedSize(22, 22)
        self.purge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.purge_btn.setToolTip("Expurgar workspace gerenciado deste terminal")
        self.purge_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none; padding: 0;
            }}
            QPushButton:hover {{ background: {DANGER}; border-radius: 2px; }}
        """)
        self.purge_btn.clicked.connect(self.purge_clicked.emit)
        self.purge_btn.hide()
        layout.addWidget(self.purge_btn)

        self.compact_btn = QPushButton()
        self.compact_btn.setIcon(get_icon("square", color=TEXT_MUTED, size=14))
        self.compact_btn.setIconSize(QSize(14, 14))
        self.compact_btn.setFixedSize(22, 22)
        self.compact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.compact_btn.setToolTip("Compactar preview")
        self.compact_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none; padding: 0;
            }}
            QPushButton:hover {{ background: {BG_ELEVATED}; border-radius: 2px; }}
        """)
        self.compact_btn.clicked.connect(self.compact_clicked.emit)
        self.compact_btn.hide()
        layout.addWidget(self.compact_btn)

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

    def set_type_icon(self, icon_name: str, light_mode: bool = False):
        """Define o icone SVG do tipo (PowerShell/Claude/etc). Sobrescreve
        qualquer setIcon legado. light_mode controla a cor (escuro em fundo
        claro, claro em fundo escuro)."""
        self._type_icon_name = icon_name or ""
        if not icon_name:
            self.icon.setHidden(True)
            return
        color = TEXT_SECONDARY if not light_mode else "#3a3a3a"
        self.icon.setPixmap(get_icon(icon_name, color=color, size=16).pixmap(16, 16))
        self.icon.setHidden(False)

    def set_icon(self, text):
        # Stub mantido pra compat com session restore (campo "icon" string
        # legado); ignorado porque agora usamos SVG do tipo do widget.
        pass

    def show_font_controls(self):
        self.font_down_btn.show()
        self.font_up_btn.show()

    def show_role_btn(self):
        self.role_btn.show()

    def show_inbox_btn(self):
        # Visivel apos primeira atualizacao; comeca mostrando "📥 0" so se count > 0.
        # show_inbox_btn so habilita o fluxo — set_pending_count controla visibilidade.
        pass

    def show_chain_btn(self):
        self.chain_btn.show()

    def show_purge_btn(self):
        self.purge_btn.show()

    def show_compact_btn(self):
        self.compact_btn.show()

    def set_pending_count(self, count):
        """Atualiza badge. Esconde quando 0, mostra com numero quando > 0."""
        count = max(0, int(count))
        self.inbox_btn.setText(f"📥 {count}")
        self._update_inbox_btn_style(count)
        self.inbox_btn.setVisible(count > 0)

    def _update_inbox_btn_style(self, count):
        bg     = ACCENT if count > 0 else "transparent"
        color  = "white" if count > 0 else TEXT_MUTED
        self.inbox_btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {color};
                border: none; border-radius: 10px;
                padding: 2px 8px;
                font-size: 9pt; font-weight: 600;
            }}
            QPushButton:hover {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY}; }}
        """)

    def _apply_style(self):
        if self._light_mode:
            bg = "#e6e6e6"
            border = "#d4d4d4"
        else:
            bg = BG_ELEVATED
            border = BORDER
        self.setStyleSheet(f"""
            NodeHeader {{ background: {bg};
                         border-bottom: 1px solid {border};
                         border-top-left-radius: 10px;
                         border-top-right-radius: 10px; }}
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
        # Branco em dark, preto em light pra contraste maximo em qualquer tema.
        active_color = "#000000" if self._light_mode else "#ffffff"
        muted_color  = "#888888" if self._light_mode else "#555555"
        if self._is_focused:
            # ativo: cor solida, fonte maior, bold (efeito glow)
            self.dot.setStyleSheet(
                f"color: {active_color}; font-size: 11pt; font-weight: bold;"
                f" background: transparent;"
            )
        else:
            # idle: cor muted
            self.dot.setStyleSheet(
                f"color: {muted_color}; font-size: 9pt; background: transparent;"
            )

    def set_light_mode(self, enabled: bool):
        """Atualiza cor do dot indicador e background do header conforme tema."""
        self._light_mode = bool(enabled)
        self._apply_style()
        self._refresh_dot()

    def set_compacted(self, compacted: bool):
        self._is_compacted = bool(compacted)
        self.setFixedHeight(80 if compacted else 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor if compacted else Qt.CursorShape.OpenHandCursor)
        self.dot.setVisible(not compacted)
        self.title.setVisible(not compacted)
        self.font_down_btn.setVisible(False if compacted else self.font_down_btn.isVisible())
        self.font_up_btn.setVisible(False if compacted else self.font_up_btn.isVisible())
        self.role_btn.setVisible(False if compacted else self.role_btn.isVisible())
        self.inbox_btn.setVisible(False if compacted else self.inbox_btn.isVisible())
        self.chain_btn.setVisible(False if compacted else self.chain_btn.isVisible())
        self.purge_btn.setVisible(False if compacted else self.purge_btn.isVisible())
        self.close_btn.setVisible(not compacted)
        self.compact_btn.setVisible(not compacted)

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
            self.drag_finished.emit()

    def mouseReleaseEvent(self, event):
        self._end_drag()
        super().mouseReleaseEvent(event)


class ResizeGrip(QWidget):
    resize_moved    = pyqtSignal(QPointF)
    resize_finished = pyqtSignal()

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
        if self._last_pos is not None:
            self._last_pos = None
            self.resize_finished.emit()


class NodeFrame(QFrame):
    resized = pyqtSignal(QSize)

    def __init__(self, title, inner, icon=""):
        super().__init__()
        self.inner         = inner
        self._focused      = False
        self._light_mode   = False
        self._node_color   = ACCENT  # sobrescrito por canvas.add_node com a accent global
        self._compacted    = False
        self._expanded_size = None
        self._compact_click_pos = None
        self.setObjectName("node")
        self.setMinimumSize(260, 180)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.header = NodeHeader(title, icon=icon)
        # Aplica o icone SVG do tipo (PowerShell/Claude/Note/etc) baseado no
        # widget interno. Substitui o slot de emoji/texto que existia antes.
        self.header.set_type_icon(_icon_for_inner(inner), light_mode=self._light_mode)
        main.addWidget(self.header)

        self.body = QWidget()
        self._apply_body_style()
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(inner)
        main.addWidget(self.body, 1)

        self.grip = ResizeGrip()
        self.grip.setParent(self)
        self.grip.raise_()

        self._apply_style()

    def set_compactable(self, enabled: bool):
        if enabled:
            self.header.show_compact_btn()
            self.header.compact_clicked.connect(self.toggle_compacted)

    def toggle_compacted(self):
        self.set_compacted(not self._compacted)

    def set_compacted(self, compacted: bool):
        if self._compacted == bool(compacted):
            return
        self._compacted = bool(compacted)
        if compacted:
            self._expanded_size = QSize(self.width(), self.height())
            self.body.hide()
            self.grip.hide()
            self.setMinimumSize(80, 80)
            self.setMaximumSize(80, 80)
            self.resize(80, 80)
            self.header.set_compacted(True)
        else:
            self.setMaximumSize(16777215, 16777215)
            self.setMinimumSize(260, 180)
            self.header.set_compacted(False)
            self.body.show()
            self.grip.show()
            target = self._expanded_size or QSize(640, 520)
            self.resize(max(260, target.width()), max(180, target.height()))
        self.resized.emit(self.size())

    def mousePressEvent(self, event):
        if self._compacted and event.button() == Qt.MouseButton.LeftButton:
            self._compact_click_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._compacted and event.button() == Qt.MouseButton.LeftButton and self._compact_click_pos is not None:
            delta = event.position().toPoint() - self._compact_click_pos
            self._compact_click_pos = None
            if abs(delta.x()) <= 4 and abs(delta.y()) <= 4:
                self.toggle_compacted()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def _apply_style(self):
        # Borda usa a accent global quando o node esta focado; neutra caso contrario.
        neutral_border = "#d4d4d4" if self._light_mode else BORDER
        bg = "#ffffff" if self._light_mode else BG_SURFACE
        border = safe_border_color(self._node_color) if self._focused else neutral_border
        width  = 2 if self._focused else 1
        self.setStyleSheet(f"""
            #node {{ background: {bg}; border: {width}px solid {border}; border-radius: 10px; }}
        """)

    def _apply_body_style(self):
        bg = "#ffffff" if self._light_mode else BG_SURFACE
        self.body.setStyleSheet(f"QWidget {{ background: {bg}; }}")

    def set_node_color(self, color):
        self._node_color = color
        self._apply_style()

    def set_focused(self, focused):
        if self._focused == focused:
            return
        self._focused = focused
        self._apply_style()
        self.header.set_focused(focused)

    def icon_text(self):
        # Compat com session.py: o icone agora vem do tipo do widget (SVG),
        # nao mais de um campo de texto editavel.
        return ""

    def set_light_mode(self, enabled: bool):
        """Atualiza icone do tipo, dot indicador, frame, body e widget interno conforme tema."""
        self._light_mode = bool(enabled)
        self._apply_style()
        self._apply_body_style()
        self.header.set_type_icon(self.header._type_icon_name, light_mode=self._light_mode)
        self.header.set_light_mode(self._light_mode)
        if hasattr(self.inner, "set_light_mode"):
            self.inner.set_light_mode(self._light_mode)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grip.move(
            self.width()  - self.grip.width()  - 2,
            self.height() - self.grip.height() - 2,
        )
        self.resized.emit(event.size())

"""TerminalsSidebar — lista vertical de terminais abertos + secao de snapshots.

Layout:
- Header "TERMINAIS" (estatico)
- Lista de terminal chips
- Header "SNAPSHOTS" + botao "+"
- Lista de snapshot chips com menu de 3 pontinhos (renomear/sobrescrever/deletar)
"""

from datetime import datetime

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
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


class SidebarChip(QFrame):
    """Chip vertical para a sidebar — mais alto, full-width."""

    clicked         = pyqtSignal()
    close_requested = pyqtSignal()

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

        self.close_btn = QPushButton()
        self.close_btn.setIcon(get_icon("close", color=TEXT_MUTED, size=12))
        self.close_btn.setIconSize(QSize(12, 12))
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent;
                          border: none; padding: 0; }}
            QPushButton:hover {{ background: {DANGER}; border-radius: 2px; }}
        """)
        self.close_btn.clicked.connect(self.close_requested.emit)
        # impede que o clique no X dispare o foco do chip (mousePressEvent do pai)
        self.close_btn.mousePressEvent = self._close_btn_mouse_press
        layout.addWidget(self.close_btn)

    def _close_btn_mouse_press(self, event):
        # consome o evento para nao propagar ao chip (que emitiria 'clicked')
        QPushButton.mousePressEvent(self.close_btn, event)
        event.accept()

    def _apply_style(self, focused):
        border = safe_border_color(self._accent_color) if focused else BORDER
        bg     = BG_ELEVATED if focused else "transparent"
        self.setStyleSheet(f"""
            #schip {{ background: {bg}; border: 1px solid {border}; border-radius: 6px; }}
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
        self.setObjectName("snapchip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(54)
        self.setStyleSheet(f"""
            #snapchip {{ background: transparent;
                        border: 1px solid {BORDER}; border-radius: 6px; }}
            #snapchip:hover {{ background: {BG_ELEVATED}; border-color: {BORDER_HOVER}; }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 6, 8)
        layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self.name_label = QLabel(info["name"])
        self.name_label.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-family: 'Segoe UI';
            font-size: 9.5pt; font-weight: 500; background: transparent;
        """)
        self.name_label.setMaximumWidth(180)
        text_col.addWidget(self.name_label)

        node_count = info.get("node_count", 0)
        modified_at = info.get("modified_at", 0)
        when = datetime.fromtimestamp(modified_at).strftime("%d/%m %H:%M") if modified_at else "?"
        meta_text = f"{node_count} node{'s' if node_count != 1 else ''} · {when}"
        self.meta_label = QLabel(meta_text)
        self.meta_label.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-family: 'Segoe UI';
            font-size: 7.5pt; background: transparent;
        """)
        self.meta_label.setMaximumWidth(180)
        text_col.addWidget(self.meta_label)

        layout.addLayout(text_col, 1)

        self.menu_btn = QPushButton("⋮")
        self.menu_btn.setFixedSize(22, 22)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SECONDARY};
                border: none; padding: 0; font-size: 13pt;
            }}
            QPushButton:hover {{ background: {BG_SURFACE}; border-radius: 2px;
                                color: {TEXT_PRIMARY}; }}
        """)
        self.menu_btn.clicked.connect(self._show_menu)
        # consome o clique para nao propagar pra mousePressEvent do chip
        self.menu_btn.mousePressEvent = self._menu_btn_mouse_press
        layout.addWidget(self.menu_btn)

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


class TerminalsSidebar(QWidget):
    """Sidebar vertical com lista de terminais e snapshots."""

    terminal_clicked = pyqtSignal(object)
    collapse_toggled = pyqtSignal(bool)

    snapshot_save_requested      = pyqtSignal()        # botao "+" header
    snapshot_load_requested      = pyqtSignal(str)
    snapshot_rename_requested    = pyqtSignal(str)
    snapshot_overwrite_requested = pyqtSignal(str)
    snapshot_delete_requested    = pyqtSignal(str)

    DEFAULT_WIDTH = 240

    def __init__(self):
        super().__init__()
        self.chips = {}
        self._snap_chips = []
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

        # Header com brand
        outer.addWidget(self._make_section_header("TERMINAIS"))

        # Lista scrollavel — duas secoes (terminais + snapshots) numa unica scroll area
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

        # Empty-state label dos terminais
        self._empty = QLabel("Nenhum terminal aberto.\nUse os botoes da topbar.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; background: transparent;
            padding: 20px;
        """)
        self._col.addWidget(self._empty)

        # Sub-header de snapshots dentro do scroll (nao no header geral, pra rolar junto)
        snap_header = QWidget()
        snap_header.setFixedHeight(32)
        snap_header.setStyleSheet(f"background: transparent; border-top: 1px solid {BORDER};")
        sh = QHBoxLayout(snap_header)
        sh.setContentsMargins(6, 0, 6, 0)
        sh.setSpacing(4)
        snap_title = QLabel("SNAPSHOTS")
        snap_title.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; font-weight: 600;
            letter-spacing: 1.5px; background: transparent;
        """)
        sh.addWidget(snap_title, 1)
        self._save_btn = QPushButton("+")
        self._save_btn.setFixedSize(22, 22)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setToolTip("Salvar canvas atual como snapshot (Ctrl+S)")
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SECONDARY};
                border: 1px solid {BORDER}; border-radius: 3px;
                font-size: 11pt; font-weight: 600;
            }}
            QPushButton:hover {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                border-color: {BORDER_HOVER};
            }}
        """)
        self._save_btn.clicked.connect(self.snapshot_save_requested.emit)
        sh.addWidget(self._save_btn)
        self._col.addWidget(snap_header)

        # Empty-state dos snapshots
        self._snap_empty = QLabel("Nenhum snapshot.\nClique '+' pra salvar o canvas atual.")
        self._snap_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._snap_empty.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; background: transparent;
            padding: 16px 12px;
        """)
        self._col.addWidget(self._snap_empty)

        self._col.addStretch()

        scroll.setWidget(self._inner)
        outer.addWidget(scroll, 1)

    def _make_section_header(self, text: str) -> QWidget:
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: transparent; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 8, 0)
        hl.setSpacing(8)

        brand = QLabel(text)
        brand.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; font-weight: 600;
            letter-spacing: 1.5px; background: transparent;
        """)
        hl.addWidget(brand, 1)
        return header

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

        # Adiciona novos terminais (insercao antes do empty-state dos terminais,
        # que e indice 0 entao inserimos sempre no fim do bloco de chips de terminal,
        # ou seja antes do empty-state dos terminais que fica em index 0...
        # estrategia mais simples: insere antes do empty no fluxo atual)
        for _, frame in terminals:
            if frame not in self.chips:
                chip = SidebarChip(frame)
                chip.clicked.connect(lambda f=frame: self.terminal_clicked.emit(f))
                chip.close_requested.connect(lambda f=frame: canvas._close(f))
                frame.inner.activity_changed.connect(
                    lambda act, c=chip: c.set_activity(act)
                )
                frame.header.title_changed.connect(
                    lambda t, c=chip: c.set_title(t)
                )
                frame.header.color_picked.connect(
                    lambda c, ch=chip: ch.set_accent(c, custom=True)
                )
                # insere antes do empty-state dos terminais (index 0)
                self._col.insertWidget(0, chip)
                self.chips[frame] = chip
                chip.set_activity(frame.inner.activity)

        # Atualiza foco
        for frame, chip in self.chips.items():
            chip.set_focused(frame is canvas.focused_frame)

        # Empty-state visibility
        self._empty.setVisible(len(self.chips) == 0)

    def set_snapshots(self, snapshots: list):
        """Re-renderiza a lista de snapshot chips. Chamado depois de save/delete/rename."""
        # Limpa chips existentes
        for chip in self._snap_chips:
            chip.setParent(None)
            chip.deleteLater()
        self._snap_chips = []

        # Posicao de insercao: depois do snap_empty (que e antes do stretch).
        # Estrutura do layout: [terminal chips...] [empty terminais] [snap header] [snap empty] [snap chips...] [stretch]
        insert_at = self._col.indexOf(self._snap_empty) + 1

        for info in snapshots:
            chip = SnapshotChip(info)
            chip.load_requested.connect(self.snapshot_load_requested.emit)
            chip.rename_requested.connect(self.snapshot_rename_requested.emit)
            chip.overwrite_requested.connect(self.snapshot_overwrite_requested.emit)
            chip.delete_requested.connect(self.snapshot_delete_requested.emit)
            self._col.insertWidget(insert_at, chip)
            insert_at += 1
            self._snap_chips.append(chip)

        self._snap_empty.setVisible(len(snapshots) == 0)

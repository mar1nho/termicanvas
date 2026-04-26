"""Modais: TerminalLaunchDialog, RoleEditorDialog."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .agents import AGENT_KINDS
from .config import DEFAULT_CWD, get_last_custom_cwd
from .roles import list_roles
from .tokens import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_PRESS,
    BG_ELEVATED,
    BG_SIDEBAR,
    BORDER,
    BORDER_HOVER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class TerminalLaunchDialog(QDialog):
    """Modal para criar terminal (com ou sem agente).

    agent_kind=None        -> terminal puro (PowerShell/CMD)
    agent_kind="claude"    -> Claude Code interativo
    agent_kind="gemini"    -> Gemini CLI interativo
    """

    def __init__(self, shell_label, default_name="", parent=None, agent_kind=None):
        super().__init__(parent)
        self._agent_kind = agent_kind
        is_agent = agent_kind in AGENT_KINDS

        title_text = (
            f"Novo agente {AGENT_KINDS[agent_kind]['label']}"
            if is_agent else f"Novo {shell_label}"
        )
        self.setWindowTitle(title_text)
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_SIDEBAR}; }}
            QLabel  {{ color: {TEXT_PRIMARY}; background: transparent; }}
        """)

        initial = get_last_custom_cwd() or DEFAULT_CWD
        self._chosen_cwd  = initial
        self._default_name = default_name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(14)

        title = QLabel(title_text)
        title.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-family: 'Segoe UI';
            font-size: 12pt; font-weight: 600; background: transparent;
        """)
        layout.addWidget(title)

        # Nome + icone na mesma linha
        layout.addWidget(self._caption("Nome do terminal:"))

        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText("ICN")
        self.icon_input.setMaxLength(4)
        self.icon_input.setFixedWidth(56)
        self.icon_input.setStyleSheet(self._input_style())
        if is_agent:
            self.icon_input.setText(AGENT_KINDS[agent_kind].get("icon", ""))
        name_row.addWidget(self.icon_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(default_name or "Nome opcional")
        self.name_input.setStyleSheet(self._input_style())
        name_row.addWidget(self.name_input, 1)

        layout.addLayout(name_row)

        # Detector automatico de manifesto + criacao opcional de role.
        # Logica: se <cwd>/<manifest> existe -> usa direto sem perguntar.
        # Se nao existe -> oferece checkbox "criar role gerenciado" + combo.
        self.role_combo            = None
        self._create_role_check    = None
        self._manifest_status      = None
        self._manifest_detected    = False  # atualizado em _refresh_manifest_status()
        if is_agent:
            layout.addSpacing(4)
            self._manifest_status = QLabel("")
            self._manifest_status.setWordWrap(True)
            self._manifest_status.setStyleSheet(f"""
                color: {TEXT_PRIMARY}; font-size: 9pt; background: {BG_ELEVATED};
                border: 1px solid {BORDER}; border-radius: 6px; padding: 10px 12px;
            """)
            layout.addWidget(self._manifest_status)

            self._create_role_check = QCheckBox(
                "Criar role gerenciado (TermiCanvas injeta como primeira mensagem)"
            )
            self._create_role_check.setStyleSheet(f"""
                QCheckBox {{
                    color: {TEXT_PRIMARY}; font-size: 9.5pt;
                    spacing: 8px; background: transparent;
                }}
                QCheckBox::indicator {{ width: 14px; height: 14px; }}
            """)
            layout.addWidget(self._create_role_check)

            self._role_caption = self._caption("    Role:")
            layout.addWidget(self._role_caption)
            self.role_combo = QComboBox()
            self.role_combo.setStyleSheet(self._combo_style())
            self.role_combo.addItem("(livre — sem role especifico)", userData=None)
            for role in list_roles():
                self.role_combo.addItem(role.name, userData=role.name)
            layout.addWidget(self.role_combo)

            self._create_role_check.toggled.connect(self._on_create_role_toggled)
            # estado inicial e definido apos _set_path inicial via _refresh_manifest_status

        layout.addSpacing(4)
        layout.addWidget(self._caption("Diretorio de trabalho:"))

        self.path_label = QLabel(initial)
        self.path_label.setStyleSheet(f"""
            background: {BG_ELEVATED}; border: 1px solid {BORDER};
            border-radius: 2px;
            padding: 10px 12px; color: {TEXT_PRIMARY};
            font-family: 'Cascadia Mono','Consolas',monospace;
            font-size: 9.5pt;
        """)
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        row = QHBoxLayout()
        row.setSpacing(8)

        default_btn = self._ghost("Pasta padrao (dattos-ia)")
        default_btn.clicked.connect(lambda: self._set_path(DEFAULT_CWD))
        row.addWidget(default_btn)

        browse_btn = self._ghost("Escolher outra...")
        browse_btn.clicked.connect(self._browse)
        row.addWidget(browse_btn)

        layout.addLayout(row)
        layout.addSpacing(8)

        footer = QHBoxLayout()
        footer.addStretch()

        cancel = self._ghost("Cancelar")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)

        confirm_label = "Iniciar agente" if is_agent else "Abrir terminal"
        ok = self._primary(confirm_label)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        footer.addWidget(ok)

        layout.addLayout(footer)

        # Detecta manifesto agora que toda a UI ja foi montada
        if is_agent:
            self._refresh_manifest_status()

        # Ajusta dialogo ao tamanho natural — evita warnings de geometry
        # quando MINMAXINFO entra em conflito com o tamanho desejado
        self.adjustSize()

    def _caption(self, text):
        c = QLabel(text)
        c.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; font-weight: 600;
            letter-spacing: 1.2px; background: transparent;
        """)
        return c

    def _input_style(self):
        return f"""
            QLineEdit {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                border: 1px solid {BORDER}; border-radius: 2px;
                padding: 10px 12px;
                font-family: 'Segoe UI'; font-size: 10pt;
            }}
            QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
        """

    def _on_create_role_toggled(self):
        if self._create_role_check is None:
            return
        show = self._create_role_check.isChecked()
        self._role_caption.setVisible(show)
        self.role_combo.setVisible(show)

    def _refresh_manifest_status(self):
        """Atualiza UI do agente baseado em existencia de CLAUDE.md/GEMINI.md no cwd."""
        if not self._agent_kind or self._manifest_status is None:
            return
        manifest = AGENT_KINDS[self._agent_kind]["manifest"]
        manifest_path = os.path.join(self._chosen_cwd, manifest)
        self._manifest_detected = os.path.isfile(manifest_path)

        if self._manifest_detected:
            self._manifest_status.setText(
                f"✓ {manifest} detectado nesta pasta — o agente vai usar o "
                f"contexto do projeto. Nenhum role gerenciado necessario."
            )
            self._manifest_status.setStyleSheet(f"""
                color: {TEXT_PRIMARY}; font-size: 9pt;
                background: {BG_ELEVATED}; border: 1px solid {ACCENT};
                border-radius: 6px; padding: 10px 12px;
            """)
            # Esconde a opcao de role
            self._create_role_check.setVisible(False)
            self._create_role_check.setChecked(False)
            self._role_caption.setVisible(False)
            self.role_combo.setVisible(False)
        else:
            self._manifest_status.setText(
                f"⚠ Esta pasta nao tem {manifest}. Voce pode criar um role "
                f"gerenciado pelo TermiCanvas (injetado como primeira mensagem "
                f"ao agente)."
            )
            self._manifest_status.setStyleSheet(f"""
                color: {TEXT_PRIMARY}; font-size: 9pt;
                background: {BG_ELEVATED}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 10px 12px;
            """)
            self._create_role_check.setVisible(True)
            # combo segue estado do checkbox
            self._on_create_role_toggled()

    def _combo_style(self):
        return f"""
            QComboBox {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                border: 1px solid {BORDER}; border-radius: 2px;
                padding: 8px 12px; font-family: 'Segoe UI'; font-size: 10pt;
            }}
            QComboBox:focus {{ border: 1px solid {ACCENT}; }}
            QComboBox QAbstractItemView {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                selection-background-color: {ACCENT}; border: 1px solid {BORDER};
            }}
        """

    def _ghost(self, text):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_SECONDARY};
                          border: 1px solid {BORDER}; border-radius: 2px;
                          padding: 9px 14px;
                          font-family: 'Segoe UI'; font-size: 10pt; }}
            QPushButton:hover {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                                border: 1px solid {BORDER_HOVER}; }}
        """)
        return b

    def _primary(self, text):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{ background: {ACCENT}; color: white; border: none;
                          border-radius: 2px;
                          padding: 10px 18px; font-family: 'Segoe UI';
                          font-size: 10pt; font-weight: 500; }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
            QPushButton:pressed {{ background: {ACCENT_PRESS}; }}
        """)
        return b

    def _set_path(self, p):
        self._chosen_cwd = p
        self.path_label.setText(p)
        self._refresh_manifest_status()

    def _browse(self):
        start = self._chosen_cwd if os.path.isdir(self._chosen_cwd) else DEFAULT_CWD
        p = QFileDialog.getExistingDirectory(
            self, "Escolha uma pasta", start,
            QFileDialog.Option.ShowDirsOnly,
        )
        if p:
            self._set_path(p)

    def chosen_cwd(self):
        return self._chosen_cwd

    def chosen_name(self):
        name = self.name_input.text().strip()
        return name or self._default_name

    def chosen_icon(self):
        return self.icon_input.text().strip()

    def chosen_role(self):
        # Role so e usado quando manifest_mode == "managed"
        if self.chosen_manifest_mode() != "managed" or self.role_combo is None:
            return None
        return self.role_combo.currentData()

    def chosen_manifest_mode(self):
        """Retorna 'existing' ou 'managed'.

        Regra:
        - Se manifesto (CLAUDE.md/GEMINI.md) existe no cwd -> "existing" (sempre)
        - Se nao existe E checkbox 'criar role' marcado -> "managed"
        - Caso contrario -> "existing"
        """
        if self._create_role_check is None:
            return "existing"
        if self._manifest_detected:
            return "existing"
        return "managed" if self._create_role_check.isChecked() else "existing"


class RoleEditorDialog(QDialog):
    """Editor inline do role.md gerenciado pelo TermiCanvas.

    Le o conteudo de <cwd>/.termicanvas/role.md, permite editar e salva no mesmo
    arquivo. Mudancas tem efeito na proxima vez que o agente ler o manifesto
    (basta reiniciar o claude/gemini ou pedir pra ele recarregar).
    """

    def __init__(self, role_path, parent=None):
        super().__init__(parent)
        self._role_path = role_path
        self.setWindowTitle(f"Editar role — {role_path.name}")
        self.setModal(True)
        self.resize(720, 560)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_SIDEBAR}; }}
            QLabel  {{ color: {TEXT_PRIMARY}; background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel("Editar role gerenciado")
        title.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-family: 'Segoe UI';
            font-size: 12pt; font-weight: 600; background: transparent;
        """)
        layout.addWidget(title)

        path_lbl = QLabel(str(role_path))
        path_lbl.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-family: 'Cascadia Mono','Consolas',monospace;
            font-size: 8.5pt; background: transparent;
        """)
        layout.addWidget(path_lbl)

        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                border: 1px solid {BORDER}; border-radius: 2px;
                padding: 12px; selection-background-color: {ACCENT};
                font-family: 'Cascadia Mono','Consolas',monospace; font-size: 10pt;
            }}
            QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
        """)
        try:
            self.editor.setPlainText(role_path.read_text(encoding="utf-8"))
        except Exception as e:
            self.editor.setPlainText(f"# erro ao ler {role_path}\n# {e}\n")
        layout.addWidget(self.editor, 1)

        footer = QHBoxLayout()
        footer.addStretch()

        cancel = QPushButton("Cancelar")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_SECONDARY};
                          border: 1px solid {BORDER}; border-radius: 2px;
                          padding: 9px 14px; font-size: 10pt; }}
            QPushButton:hover {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                                border: 1px solid {BORDER_HOVER}; }}
        """)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)

        save = QPushButton("Salvar")
        save.setDefault(True)
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setStyleSheet(f"""
            QPushButton {{ background: {ACCENT}; color: white; border: none;
                          border-radius: 2px; padding: 10px 18px;
                          font-size: 10pt; font-weight: 500; }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
            QPushButton:pressed {{ background: {ACCENT_PRESS}; }}
        """)
        save.clicked.connect(self._save)
        footer.addWidget(save)

        layout.addLayout(footer)

    def _save(self):
        try:
            self._role_path.parent.mkdir(parents=True, exist_ok=True)
            self._role_path.write_text(self.editor.toPlainText(), encoding="utf-8")
            self.accept()
        except Exception as e:
            self.editor.setPlainText(self.editor.toPlainText() + f"\n\n[erro ao salvar: {e}]")

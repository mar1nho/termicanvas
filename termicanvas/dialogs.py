"""Modais: TerminalLaunchDialog, RoleEditorDialog."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .agents import AGENT_KINDS
from .config import get_default_cwd, get_last_custom_cwd
from .preview import MODE_AUTO, MODE_HTML, MODE_MARKDOWN
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
    agent_kind="codex"     -> Codex CLI interativo
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

        initial = get_last_custom_cwd() or get_default_cwd()
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
        self._orchestrator_check   = None
        self._manifest_status      = None
        self._manifest_detected    = False  # atualizado em _refresh_manifest_status()
        self.shell_combo           = None
        if is_agent:
            layout.addSpacing(4)
            layout.addWidget(self._caption("Shell:"))
            self.shell_combo = QComboBox()
            self.shell_combo.setStyleSheet(self._combo_style())
            self.shell_combo.addItem("PowerShell", userData="powershell.exe")
            self.shell_combo.addItem("CMD", userData="cmd.exe")
            layout.addWidget(self.shell_combo)

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

            # Checkbox de orquestrador — apende um system prompt ao manifesto
            # com instrucoes pra coordenar outros agentes via bus.
            # Independente do checkbox de role (funciona ate com manifesto ja
            # existente, porque so apende um bloco marcado no final).
            self._orchestrator_check = QCheckBox(
                "Promover a Orquestrador (apende prompt de coordenacao no manifesto)"
            )
            self._orchestrator_check.setStyleSheet(f"""
                QCheckBox {{
                    color: {TEXT_PRIMARY}; font-size: 9.5pt;
                    spacing: 8px; background: transparent;
                }}
                QCheckBox::indicator {{ width: 14px; height: 14px; }}
            """)
            self._orchestrator_check.setToolTip(
                "Adiciona ao final do manifesto do agente instrucoes sobre como "
                "listar agentes, enviar mensagens, broadcast e consultar inbox."
            )
            layout.addWidget(self._orchestrator_check)

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

        default_btn = self._ghost("Pasta padrao")
        default_btn.clicked.connect(lambda: self._set_path(get_default_cwd()))
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
        """Atualiza UI do agente baseado em existencia de manifesto no cwd."""
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
        start = self._chosen_cwd if os.path.isdir(self._chosen_cwd) else get_default_cwd()
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

    def chosen_shell(self):
        if self.shell_combo is None:
            return None
        return self.shell_combo.currentData() or "powershell.exe"

    def chosen_orchestrator(self):
        """True se o usuario marcou pra promover a orquestrador."""
        return bool(self._orchestrator_check and self._orchestrator_check.isChecked())

    def chosen_role(self):
        # Role so e usado quando manifest_mode == "managed"
        if self.chosen_manifest_mode() != "managed" or self.role_combo is None:
            return None
        return self.role_combo.currentData()

    def chosen_manifest_mode(self):
        """Retorna 'existing' ou 'managed'.

        Regra:
        - Se manifesto existe no cwd -> "existing" (sempre)
        - Se nao existe E checkbox 'criar role' marcado -> "managed"
        - Caso contrario -> "existing"
        """
        if self._create_role_check is None:
            return "existing"
        if self._manifest_detected:
            return "existing"
        return "managed" if self._create_role_check.isChecked() else "existing"


class UnifiedLaunchDialog(QDialog):
    """Dialogo unico para escolher o tipo de terminal/agente antes de inserir."""

    KIND_ITEMS = [
        ("PowerShell", "powershell"),
        ("CMD", "cmd"),
        ("Claude Code", "claude"),
        ("Codex CLI", "codex"),
        ("Gemini CLI", "gemini"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo terminal/agente")
        self.setModal(True)
        self.setFixedWidth(460)
        self.setMaximumHeight(680)
        self._chosen_cwd = get_last_custom_cwd() or get_default_cwd()
        self._manifest_detected = False
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_SIDEBAR}; }}
            QLabel  {{ color: {TEXT_PRIMARY}; background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(9)

        title = QLabel("Novo terminal/agente")
        title.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-family: 'Segoe UI';
            font-size: 11pt; font-weight: 600; background: transparent;
        """)
        layout.addWidget(title)

        layout.addWidget(self._caption("Tipo:"))
        self.kind_group = QButtonGroup(self)
        self.kind_group.setExclusive(True)
        kind_grid = QGridLayout()
        kind_grid.setSpacing(6)
        self.kind_buttons = {}
        for idx, (label, kind) in enumerate(self.KIND_ITEMS):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._choice_style())
            self.kind_group.addButton(btn)
            self.kind_buttons[kind] = btn
            kind_grid.addWidget(btn, idx // 3, idx % 3)
        self.kind_buttons["powershell"].setChecked(True)
        self.kind_group.buttonClicked.connect(self._refresh_kind_ui)
        layout.addLayout(kind_grid)

        layout.addWidget(self._caption("Nome:"))
        self.name_input = QLineEdit()
        self.name_input.setStyleSheet(self._input_style())
        layout.addWidget(self.name_input)

        self.shell_caption = self._caption("Shell do agente:")
        layout.addWidget(self.shell_caption)
        self.shell_combo = QComboBox()
        self.shell_combo.setStyleSheet(self._combo_style())
        self.shell_combo.addItem("PowerShell", "powershell.exe")
        self.shell_combo.addItem("CMD", "cmd.exe")
        layout.addWidget(self.shell_combo)

        self._manifest_status = QLabel("")
        self._manifest_status.setWordWrap(True)
        self._manifest_status.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-size: 9pt; background: {BG_ELEVATED};
            border: 1px solid {BORDER}; border-radius: 6px; padding: 8px 10px;
        """)
        layout.addWidget(self._manifest_status)

        self._create_role_check = QCheckBox("Criar role gerenciado quando nao houver manifesto")
        self._create_role_check.setStyleSheet(self._check_style())
        self._create_role_check.toggled.connect(self._on_create_role_toggled)
        layout.addWidget(self._create_role_check)

        self._role_caption = self._caption("Role:")
        layout.addWidget(self._role_caption)
        self.role_combo = QComboBox()
        self.role_combo.setStyleSheet(self._combo_style())
        self.role_combo.addItem("(livre)", None)
        for role in list_roles():
            self.role_combo.addItem(role.name, role.name)
        layout.addWidget(self.role_combo)

        self._orchestrator_check = QCheckBox("Orquestrador ativo")
        self._orchestrator_check.setStyleSheet(self._check_style())
        layout.addWidget(self._orchestrator_check)

        layout.addWidget(self._caption("Diretorio de trabalho:"))
        self.path_label = QLabel(self._chosen_cwd)
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet(f"""
            background: {BG_ELEVATED}; border: 1px solid {BORDER};
            border-radius: 2px; padding: 8px 10px; color: {TEXT_PRIMARY};
            font-family: 'Cascadia Mono','Consolas',monospace; font-size: 9.5pt;
        """)
        layout.addWidget(self.path_label)

        path_row = QHBoxLayout()
        default_btn = self._ghost("Pasta padrao")
        default_btn.clicked.connect(lambda: self._set_path(get_default_cwd()))
        path_row.addWidget(default_btn)
        browse_btn = self._ghost("Escolher outra...")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._set_default_check = QCheckBox("Definir esta pasta como padrao")
        self._set_default_check.setStyleSheet(self._check_style())
        layout.addWidget(self._set_default_check)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel = self._ghost("Cancelar")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        ok = self._primary("Armar insercao")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        footer.addWidget(ok)
        layout.addLayout(footer)

        self._refresh_kind_ui()
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
                padding: 7px 9px;
                font-family: 'Segoe UI'; font-size: 9.5pt;
            }}
            QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
        """

    def _combo_style(self):
        return TerminalLaunchDialog._combo_style(self)

    def _choice_style(self):
        return f"""
            QPushButton {{
                background: {BG_ELEVATED}; color: {TEXT_SECONDARY};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 7px 8px; font-family: 'Segoe UI'; font-size: 9pt;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY}; border-color: {BORDER_HOVER};
            }}
            QPushButton:checked {{
                background: {ACCENT}; color: white; border-color: {ACCENT};
            }}
        """

    def _ghost(self, text):
        return TerminalLaunchDialog._ghost(self, text)

    def _primary(self, text):
        return TerminalLaunchDialog._primary(self, text)

    def _check_style(self):
        return f"""
            QCheckBox {{ color: {TEXT_PRIMARY}; font-size: 9pt; spacing: 8px; background: transparent; }}
            QCheckBox::indicator {{
                width: 14px; height: 14px;
                border: 1px solid {TEXT_SECONDARY};
                background: {BG_ELEVATED};
                border-radius: 2px;
            }}
            QCheckBox::indicator:hover {{ border-color: {BORDER_HOVER}; }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border: 1px solid {ACCENT};
            }}
        """

    def _is_agent(self):
        return self.chosen_kind() in AGENT_KINDS

    def _refresh_kind_ui(self, *_args):
        is_agent = self._is_agent()
        self.shell_caption.setVisible(is_agent)
        self.shell_combo.setVisible(is_agent)
        self._manifest_status.setVisible(is_agent)
        self._create_role_check.setVisible(is_agent)
        self._role_caption.setVisible(is_agent and self._create_role_check.isChecked())
        self.role_combo.setVisible(is_agent and self._create_role_check.isChecked())
        self._orchestrator_check.setVisible(is_agent)
        self._refresh_manifest_status()

    def _on_create_role_toggled(self):
        self._refresh_kind_ui()

    def _refresh_manifest_status(self):
        if not self._is_agent():
            return
        manifest = AGENT_KINDS[self.chosen_kind()]["manifest"]
        manifest_path = os.path.join(self._chosen_cwd, manifest)
        self._manifest_detected = os.path.isfile(manifest_path)
        if self._manifest_detected:
            self._manifest_status.setText(f"{manifest} detectado nesta pasta. O agente usara o contexto do projeto.")
            self._create_role_check.setChecked(False)
            self._create_role_check.setVisible(False)
            self._role_caption.setVisible(False)
            self.role_combo.setVisible(False)
        else:
            self._manifest_status.setText(f"Esta pasta nao tem {manifest}. Voce pode criar um role gerenciado.")
            self._create_role_check.setVisible(True)

    def _set_path(self, path):
        self._chosen_cwd = path
        self.path_label.setText(path)
        self._refresh_manifest_status()

    def _browse(self):
        start = self._chosen_cwd if os.path.isdir(self._chosen_cwd) else get_default_cwd()
        path = QFileDialog.getExistingDirectory(self, "Escolha uma pasta", start, QFileDialog.Option.ShowDirsOnly)
        if path:
            self._set_path(path)

    def chosen_kind(self):
        for kind, button in self.kind_buttons.items():
            if button.isChecked():
                return kind
        return "powershell"

    def chosen_name(self):
        return self.name_input.text().strip()

    def chosen_cwd(self):
        return self._chosen_cwd

    def chosen_shell(self):
        return self.shell_combo.currentData() or "powershell.exe"

    def chosen_manifest_mode(self):
        if not self._is_agent() or self._manifest_detected:
            return "existing"
        return "managed" if self._create_role_check.isChecked() else "existing"

    def chosen_role(self):
        if self.chosen_manifest_mode() != "managed":
            return None
        return self.role_combo.currentData()

    def chosen_orchestrator(self):
        return bool(self._is_agent() and self._orchestrator_check.isChecked())

    def should_set_default_cwd(self):
        return self._set_default_check.isChecked()

    def launch_options(self):
        return {
            "kind": self.chosen_kind(),
            "name": self.chosen_name() or None,
            "cwd": self.chosen_cwd(),
            "shell": self.chosen_shell(),
            "manifest_mode": self.chosen_manifest_mode(),
            "role_name": self.chosen_role(),
            "orchestrator": self.chosen_orchestrator(),
            "set_default_cwd": self.should_set_default_cwd(),
        }


class RoleEditorDialog(QDialog):
    """Editor inline do role.md gerenciado pelo TermiCanvas.

    Le o conteudo de <cwd>/.termicanvas/role.md, permite editar e salva no mesmo
    arquivo. Mudancas tem efeito na proxima vez que o agente ler o manifesto
    (basta reiniciar o agente ou pedir pra ele recarregar).
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


class PreviewLaunchDialog(QDialog):
    """Modal de criacao do node Preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo preview")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_SIDEBAR}; }}
            QLabel  {{ color: {TEXT_PRIMARY}; background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(14)

        title = QLabel("Novo preview")
        title.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-family: 'Segoe UI';
            font-size: 12pt; font-weight: 600; background: transparent;
        """)
        layout.addWidget(title)

        layout.addWidget(self._caption("Arquivo:"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Escolha um .md, .html ou .htm")
        self.path_input.setStyleSheet(self._input_style())
        row.addWidget(self.path_input, 1)

        browse = self._ghost("Escolher...")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)

        layout.addWidget(self._caption("Tipo:"))
        self.mode_combo = QComboBox()
        self.mode_combo.setStyleSheet(self._combo_style())
        self.mode_combo.addItem("Detectar pelo arquivo", MODE_AUTO)
        self.mode_combo.addItem("Markdown", MODE_MARKDOWN)
        self.mode_combo.addItem("HTML", MODE_HTML)
        layout.addWidget(self.mode_combo)

        footer = QHBoxLayout()
        footer.addStretch()

        cancel = self._ghost("Cancelar")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)

        ok = self._primary("Criar preview")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        footer.addWidget(ok)

        layout.addLayout(footer)

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

    def _browse(self):
        start = get_default_cwd()
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Escolha um arquivo para preview",
            start,
            "Markdown/HTML (*.md *.markdown *.mdown *.html *.htm);;Todos os arquivos (*.*)",
        )
        if chosen:
            self.path_input.setText(chosen)

    def chosen_path(self):
        return self.path_input.text().strip()

    def chosen_mode(self):
        return self.mode_combo.currentData() or MODE_AUTO


class BusOffConfirmDialog(QDialog):
    """Confirma o desligamento do bus (operacao destrutiva)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Desligar bus")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_SIDEBAR}; }}
            QLabel  {{ color: {TEXT_PRIMARY}; background: transparent; }}
            QCheckBox {{ color: {TEXT_SECONDARY}; background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Desligar bus")
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12pt; font-weight: 600;")
        layout.addWidget(title)

        body = QLabel(
            "Desligar o bus vai fechar todos os terminais e widgets do canvas.\n\n"
            "Tem certeza?"
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        self._dont_ask = QCheckBox("Nao perguntar de novo")
        layout.addWidget(self._dont_ask)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._confirm_btn = QPushButton("Desligar")
        self._confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white; border: none;
                border-radius: 4px; padding: 6px 16px;
            }}
            QPushButton:hover  {{ background: {ACCENT_HOVER}; }}
            QPushButton:pressed {{ background: {ACCENT_PRESS}; }}
        """)
        self._confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._confirm_btn)

        layout.addLayout(btn_row)

    def dont_ask_again(self) -> bool:
        return self._dont_ask.isChecked()


class SnapshotNameDialog(QDialog):
    """Pede um nome para um novo snapshot. Validacao basica: nao-vazio.

    Se initial_name for passado (modo renomear), pre-preenche o input.
    """

    def __init__(self, parent=None, initial_name: str = "", title: str = "Salvar snapshot",
                 confirm_label: str = "Salvar"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_SIDEBAR}; }}
            QLabel  {{ color: {TEXT_PRIMARY}; background: transparent; }}
            QLineEdit {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 6px 8px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12pt; font-weight: 600;")
        layout.addWidget(title_lbl)

        layout.addWidget(QLabel("Nome:"))
        self._input = QLineEdit(initial_name)
        self._input.setPlaceholderText("ex: estudo claude, tarde focus, debug session")
        self._input.returnPressed.connect(self._maybe_accept)
        layout.addWidget(self._input)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._confirm_btn = QPushButton(confirm_label)
        self._confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._confirm_btn.setDefault(True)
        self._confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white; border: none;
                border-radius: 4px; padding: 6px 16px;
            }}
            QPushButton:hover  {{ background: {ACCENT_HOVER}; }}
            QPushButton:pressed {{ background: {ACCENT_PRESS}; }}
        """)
        self._confirm_btn.clicked.connect(self._maybe_accept)
        btn_row.addWidget(self._confirm_btn)

        layout.addLayout(btn_row)
        self._input.setFocus()
        self._input.selectAll()

    def _maybe_accept(self):
        if self.chosen_name():
            self.accept()

    def chosen_name(self) -> str:
        return self._input.text().strip()


class LoadSnapshotConfirmDialog(QDialog):
    """Confirma carregar um snapshot — operacao destrutiva (fecha canvas atual).

    Tres botoes: salvar e carregar / so carregar / cancelar. Mais checkbox
    'nao perguntar de novo'. accepted() retorna 1 (so carregar) ou 2 (salvar
    e carregar); rejected() = cancelar.
    """

    LOAD_ONLY = 1
    SAVE_AND_LOAD = 2

    def __init__(self, parent=None, snapshot_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Carregar snapshot")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_SIDEBAR}; }}
            QLabel  {{ color: {TEXT_PRIMARY}; background: transparent; }}
            QCheckBox {{ color: {TEXT_SECONDARY}; background: transparent; }}
        """)

        self._action = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel(f"Carregar '{snapshot_name}'")
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12pt; font-weight: 600;")
        layout.addWidget(title)

        body = QLabel(
            "Isso vai fechar todos os terminais e widgets do canvas atual.\n\n"
            "Quer salvar o canvas atual como snapshot antes?"
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        self._dont_ask = QCheckBox("Nao perguntar de novo")
        layout.addWidget(self._dont_ask)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._load_only_btn = QPushButton("So carregar")
        self._load_only_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_only_btn.clicked.connect(self._on_load_only)
        btn_row.addWidget(self._load_only_btn)

        self._save_load_btn = QPushButton("Salvar e carregar")
        self._save_load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_load_btn.setDefault(True)
        self._save_load_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white; border: none;
                border-radius: 4px; padding: 6px 16px;
            }}
            QPushButton:hover  {{ background: {ACCENT_HOVER}; }}
            QPushButton:pressed {{ background: {ACCENT_PRESS}; }}
        """)
        self._save_load_btn.clicked.connect(self._on_save_and_load)
        btn_row.addWidget(self._save_load_btn)

        layout.addLayout(btn_row)

    def _on_load_only(self):
        self._action = self.LOAD_ONLY
        self.accept()

    def _on_save_and_load(self):
        self._action = self.SAVE_AND_LOAD
        self.accept()

    def chosen_action(self) -> int:
        return self._action

    def dont_ask_again(self) -> bool:
        return self._dont_ask.isChecked()

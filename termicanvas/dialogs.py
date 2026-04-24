"""Modais: TerminalLaunchDialog."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .config import DEFAULT_CWD, get_last_custom_cwd
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
    """Modal para escolher o diretorio de trabalho do novo terminal."""

    def __init__(self, shell_label, default_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Abrir {shell_label}")
        self.setModal(True)
        self.setMinimumWidth(480)
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

        title = QLabel(f"Novo {shell_label}")
        title.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; font-family: 'Segoe UI';
            font-size: 12pt; font-weight: 600; background: transparent;
        """)
        layout.addWidget(title)

        name_cap = QLabel("Nome do terminal:")
        name_cap.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; font-weight: 600;
            letter-spacing: 1.2px; background: transparent;
        """)
        layout.addWidget(name_cap)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(default_name or "Nome opcional")
        self.name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                border: 1px solid {BORDER}; border-radius: 2px;
                padding: 10px 12px;
                font-family: 'Segoe UI'; font-size: 10pt;
            }}
            QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
        """)
        layout.addWidget(self.name_input)

        layout.addSpacing(4)

        caption = QLabel("Diretorio de trabalho:")
        caption.setStyleSheet(f"""
            color: {TEXT_MUTED}; font-size: 8.5pt; font-weight: 600;
            letter-spacing: 1.2px; background: transparent;
        """)
        layout.addWidget(caption)

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

        ok = self._primary("Abrir terminal")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        footer.addWidget(ok)

        layout.addLayout(footer)

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

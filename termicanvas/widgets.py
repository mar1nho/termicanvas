"""Widgets simples: NoteWidget, PromptCard, EditableLabel."""

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .tokens import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_PRESS,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER,
    BORDER_HOVER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class NoteWidget(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setPlaceholderText("Escreva suas anotacoes aqui...")
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_SURFACE};
                color: {TEXT_PRIMARY};
                font-family: 'Segoe UI', sans-serif;
                font-size: 10.5pt;
                border: none;
                padding: 14px;
                selection-background-color: {ACCENT};
            }}
        """)


class PromptCard(QWidget):
    route_output = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {BG_SURFACE};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._edit = QPlainTextEdit()
        self._edit.setPlaceholderText("Escreva o texto... (Ctrl+Enter envia)")
        self._edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {BG_SURFACE};
                color: {TEXT_PRIMARY};
                font-family: 'Cascadia Mono','Consolas',monospace;
                font-size: 10pt;
                border: none;
                padding: 12px 14px;
                selection-background-color: {ACCENT};
            }}
            QScrollBar:vertical {{ background: {BG_SURFACE}; width: 8px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: {BORDER_HOVER}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)
        self._edit.installEventFilter(self)
        layout.addWidget(self._edit, 1)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        layout.addWidget(sep)

        bottom = QWidget()
        bottom.setStyleSheet(f"background: {BG_SURFACE};")
        row = QHBoxLayout(bottom)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)

        self._hint = QLabel("Ctrl+Enter envia ao destino conectado")
        self._hint.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 8.5pt; background: transparent;"
        )
        row.addWidget(self._hint, 1)

        self._btn = QPushButton("Enviar ↑")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFixedHeight(28)
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white; border: none;
                border-radius: 2px; padding: 0 14px;
                font-family: 'Segoe UI'; font-size: 9.5pt; font-weight: 500;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
            QPushButton:pressed {{ background: {ACCENT_PRESS}; }}
        """)
        self._btn.clicked.connect(self._send)
        row.addWidget(self._btn)

        layout.addWidget(bottom)

    def eventFilter(self, obj, event):
        if obj is self._edit and event.type() == QEvent.Type.KeyPress:
            if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                    and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _send(self):
        text = self._edit.toPlainText().strip()
        if text:
            self.route_output.emit(text)

    def text(self):
        return self._edit.toPlainText()

    def setText(self, text):
        self._edit.setPlainText(text)


class EditableLabel(QWidget):
    text_changed = pyqtSignal(str)

    def __init__(self, text):
        super().__init__()
        self._text = text
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.label = QLabel(text)
        self._label_style = ""
        layout.addWidget(self.label)

        self.edit = QLineEdit(text)
        self.edit.hide()
        self.edit.editingFinished.connect(self._finish)
        self.edit.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_SURFACE};
                color: {TEXT_PRIMARY};
                border: 1px solid {ACCENT};
                border-radius: 2px;
                padding: 1px 4px;
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: 500;
            }}
        """)
        layout.addWidget(self.edit)

    def text(self):
        return self._text

    def set_label_style(self, style):
        self._label_style = style
        self.label.setStyleSheet(style)

    def setText(self, text):
        self._text = text
        self.label.setText(text)

    def mouseDoubleClickEvent(self, event):
        self.label.hide()
        self.edit.setText(self._text)
        self.edit.selectAll()
        self.edit.show()
        self.edit.setFocus()
        event.accept()

    def _finish(self):
        new = self.edit.text().strip() or self._text
        self.edit.hide()
        self._text = new
        self.label.setText(new)
        self.label.show()
        self.text_changed.emit(new)

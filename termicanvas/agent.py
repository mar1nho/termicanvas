"""AgentWidget: chat que dispara 'claude -p' via subprocess."""

import subprocess
import sys
import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .config import DEFAULT_CWD
from .tokens import (
    ACCENT,
    ACCENT_HOVER,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER,
    BORDER_HOVER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    readable_text_color,
)


class ChatBubble(QFrame):
    def __init__(self, text, role, bubble_bg=None):
        super().__init__()
        is_user = role == "user"
        user_bg = bubble_bg or ACCENT
        self.setStyleSheet("background: transparent;")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 3, 16, 3)
        outer.setSpacing(0)

        self._bubble = QFrame()
        self._bubble.setMaximumWidth(460)

        self._lbl = QLabel(text)
        self._lbl.setWordWrap(True)
        self._lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_color = readable_text_color(user_bg) if is_user else TEXT_PRIMARY
        self._lbl.setStyleSheet(f"""
            color: {text_color};
            font-family: 'Segoe UI'; font-size: 10pt; background: transparent;
        """)

        bl = QVBoxLayout(self._bubble)
        bl.setContentsMargins(12, 8, 12, 8)
        bl.addWidget(self._lbl)

        if is_user:
            self._bubble.setStyleSheet(f"""
                QFrame {{ background: {user_bg}; border-radius: 16px;
                         border-bottom-right-radius: 3px; }}
            """)
            outer.addStretch()
            outer.addWidget(self._bubble)
        else:
            self._bubble.setStyleSheet(f"""
                QFrame {{ background: {BG_ELEVATED}; border: 1px solid {BORDER};
                         border-radius: 16px; border-bottom-left-radius: 3px; }}
            """)
            outer.addWidget(self._bubble)
            outer.addStretch()

    def set_text(self, text):
        self._lbl.setText(text)


class AgentWidget(QWidget):
    _response_ready = pyqtSignal(str)
    route_output    = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {BG_SURFACE};")
        self._running        = False
        self._pending_bubble = None
        self.last_response   = ""
        self._response_ready.connect(self._on_response)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # área de chat
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_SURFACE}; border: none; }}
            QScrollBar:vertical {{
                background: {BG_SURFACE}; width: 6px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
        """)

        self._container = QWidget()
        self._container.setStyleSheet(f"background: {BG_SURFACE};")
        self._chat_layout = QVBoxLayout(self._container)
        self._chat_layout.setContentsMargins(0, 14, 0, 14)
        self._chat_layout.setSpacing(6)
        self._chat_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, 1)

        # separador
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        layout.addWidget(sep)

        # input
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {BG_SURFACE};")
        row = QHBoxLayout(bottom)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Pergunte algo ao Claude…")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_ELEVATED}; color: {TEXT_PRIMARY};
                border: 1px solid {BORDER}; border-radius: 2px;
                padding: 8px 16px; font-family: 'Segoe UI'; font-size: 10pt;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input, 1)

        self._btn = QPushButton("↑")
        self._btn.setFixedSize(36, 36)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white; border: none;
                border-radius: 2px; font-size: 14pt; font-weight: bold;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
            QPushButton:disabled {{ background: {BG_ELEVATED}; color: {TEXT_SECONDARY}; }}
        """)
        self._btn.clicked.connect(self._send)
        row.addWidget(self._btn)

        layout.addWidget(bottom)

        self._route_btn = QPushButton("→ próximo")
        self._route_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._route_btn.setVisible(False)
        self._route_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_MUTED};
                border: 1px solid {BORDER}; border-radius: 2px;
                padding: 3px 10px; font-size: 8.5pt;
                margin: 0 12px 8px 12px;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY}; border-color: {BORDER_HOVER};
                background: {BG_ELEVATED};
            }}
        """)
        self._route_btn.clicked.connect(lambda: self.route_output.emit(self.last_response))
        layout.addWidget(self._route_btn)

    def _add_bubble(self, text, role):
        bubble = ChatBubble(text, role, bubble_bg=self._bubble_bg())
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, bubble)
        QTimer.singleShot(40, self._scroll_bottom)
        return bubble

    def _bubble_bg(self):
        """Cor de fundo das bolhas do usuario — segue o accent do node se houver."""
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "_node_color"):
                return parent._node_color
            parent = parent.parent()
        return ACCENT

    def _scroll_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _send(self):
        msg = self._input.text().strip()
        if not msg or self._running:
            return
        self._input.clear()
        self._running = True
        self._btn.setEnabled(False)

        self._add_bubble(msg, "user")
        self._pending_bubble = self._add_bubble("digitando…", "agent")

        threading.Thread(target=self._run, args=(msg,), daemon=True).start()

    def _run(self, msg):
        try:
            if sys.platform == "win32":
                cmd    = ["cmd", "/c", "claude", "-p", "--no-session-persistence"]
                kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW}
            else:
                cmd    = ["claude", "-p", "--no-session-persistence"]
                kwargs = {}
            result = subprocess.run(
                cmd,
                input=msg,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=DEFAULT_CWD,
                **kwargs,
            )
            response = result.stdout.strip() or result.stderr.strip() or "(sem resposta)"
        except FileNotFoundError:
            response = "[erro] 'claude' não encontrado. Verifique se o Claude Code CLI está instalado."
        except subprocess.TimeoutExpired:
            response = "[erro] tempo esgotado (120s)."
        except Exception as e:
            response = f"[erro] {e}"
        self._response_ready.emit(response)

    def _on_response(self, text):
        if self._pending_bubble:
            self._pending_bubble.set_text(text)
            self._pending_bubble = None
        self.last_response = text
        self._running = False
        self._btn.setEnabled(True)
        self._route_btn.setVisible(True)
        QTimer.singleShot(50, self._scroll_bottom)

    def receive(self, text):
        self._input.setText(text)
        self._send()

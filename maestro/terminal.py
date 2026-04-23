"""TerminalWidget + PtyBridge: terminal PyQt com PTY (ConPTY via pywinpty) e pyte."""

import os
import re
import threading

import pyte
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal


class _HistoryScreen(pyte.HistoryScreen):
    def select_graphic_rendition(self, *attrs, private=False, **kwargs):
        super().select_graphic_rendition(*attrs)
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QPlainTextEdit

from .config import DEFAULT_CWD
from .tokens import ACCENT, BG_TERMINAL, BORDER, BORDER_HOVER, TEXT_PRIMARY

try:
    from winpty import PtyProcess
    PTY_OK = True
except ImportError:
    PTY_OK = False

PS_PROMPT_RE = re.compile(r"PS\s+[A-Za-z]:\\[^>]*>\s*$")


class PtyBridge(QObject):
    data_received = pyqtSignal(str)


class TerminalWidget(QPlainTextEdit):
    activity_changed = pyqtSignal(str)

    COLS      = 100
    ROWS      = 30
    HISTORY   = 3000
    RAW_LIMIT = 300_000  # chars — janela deslizante do stream bruto para re-feed no resize

    def __init__(self, shell="powershell.exe", cwd=None, startup_command=None):
        super().__init__()
        self.shell    = shell
        self.cwd      = cwd
        self.activity = ""
        self._startup_command = startup_command
        self._startup_sent    = False
        self._font_size = 10

        font = QFont("Cascadia Mono", self._font_size)
        if not font.exactMatch():
            font = QFont("Consolas", self._font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {BG_TERMINAL};
                color: {TEXT_PRIMARY};
                border: none;
                padding: 10px 12px;
                selection-background-color: {ACCENT};
            }}
            QScrollBar:vertical {{
                background: {BG_TERMINAL};
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {BORDER_HOVER}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)
        self.setUndoRedoEnabled(False)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setCursorWidth(2)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.screen = _HistoryScreen(self.COLS, self.ROWS, history=self.HISTORY, ratio=0.5)
        self.stream = pyte.Stream(self.screen)
        self.bridge = PtyBridge()
        self.bridge.data_received.connect(self._on_data)

        self._pending_cols = self.COLS
        self._pending_rows = self.ROWS
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self._do_resize)

        self._render_dirty = False
        self._last_content = ""
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(33)
        self._render_timer.timeout.connect(self._flush_render)
        self._render_timer.start()

        self._raw_buf = ""   # stream VT100 acumulado para re-feed no resize

        self.pty   = None
        self.alive = False

        if not PTY_OK:
            self.setPlainText("[erro] pywinpty nao instalado.")
            return
        QTimer.singleShot(0, self._spawn)

    def _spawn(self):
        try:
            spawn_kwargs = {"dimensions": (self._pending_rows, self._pending_cols)}
            target_cwd = self.cwd or DEFAULT_CWD
            if target_cwd and os.path.isdir(target_cwd):
                spawn_kwargs["cwd"] = target_cwd
            self.pty   = PtyProcess.spawn(self.shell, **spawn_kwargs)
            self.alive = True
            threading.Thread(target=self._read_loop, daemon=True).start()
        except Exception as e:
            self.setPlainText(f"[erro] falha ao iniciar {self.shell}: {e}")

    def _read_loop(self):
        while self.alive and self.pty:
            try:
                data = self.pty.read(4096)
                if not data:
                    break
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")
                self.bridge.data_received.emit(data)
            except EOFError:
                break
            except Exception as e:
                self.bridge.data_received.emit(f"\n[erro] {e}\n")
                break
        self.alive = False

    def _on_data(self, text):
        self._raw_buf = (self._raw_buf + text)[-self.RAW_LIMIT:]
        self.stream.feed(text)
        self._render_dirty = True
        self._check_idle()

    def _flush_render(self):
        if self._render_dirty:
            self._render_dirty = False
            self._render()

    def _row_to_str(self, row, width):
        return "".join(row[x].data for x in range(width)).rstrip()

    def _render(self):
        sb = self.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4

        history_top    = list(self.screen.history.top)
        history_bottom = list(self.screen.history.bottom)

        history_lines  = [self._row_to_str(r, self.screen.columns) for r in history_top]
        history_lines += [self._row_to_str(r, self.screen.columns) for r in history_bottom]

        screen_lines = [
            self._row_to_str(self.screen.buffer[y], self.screen.columns)
            for y in range(self.screen.lines)
        ]

        all_lines = history_lines + screen_lines
        while all_lines and not all_lines[-1]:
            all_lines.pop()
        content = "\n".join(all_lines)

        if content != self._last_content:
            self._last_content = content
            self.setPlainText(content)

        cursor_y    = len(history_lines) + self.screen.cursor.y
        line_starts = [0]
        for ln in all_lines[:-1]:
            line_starts.append(line_starts[-1] + len(ln) + 1)
        pos = len(content)
        if cursor_y < len(line_starts):
            pos = min(line_starts[cursor_y] + self.screen.cursor.x, len(content))
        cur = self.textCursor()
        cur.setPosition(pos)
        self.setTextCursor(cur)

        if at_bottom:
            sb.setValue(sb.maximum())

    def _check_idle(self):
        last_line = self._row_to_str(
            self.screen.buffer[self.screen.lines - 1], self.screen.columns
        )
        if not last_line:
            for y in range(self.screen.lines - 2, max(0, self.screen.lines - 4), -1):
                candidate = self._row_to_str(self.screen.buffer[y], self.screen.columns)
                if candidate:
                    last_line = candidate
                    break

        if PS_PROMPT_RE.search(last_line) or last_line.endswith("$ ") or last_line.endswith("# "):
            if self.activity:
                self.activity = ""
                self.activity_changed.emit("")
            if self._startup_command and not self._startup_sent:
                self._startup_sent = True
                QTimer.singleShot(200, lambda: self.send(self._startup_command))

    def keyPressEvent(self, event):
        if not (self.pty and self.alive):
            return
        key  = event.key()
        mods = event.modifiers()
        text = event.text()

        if mods & Qt.KeyboardModifier.ControlModifier and not (
            mods & Qt.KeyboardModifier.ShiftModifier
        ):
            if key == Qt.Key.Key_C:
                cursor = self.textCursor()
                if cursor.hasSelection():
                    text_sel = cursor.selectedText().replace("\u2029", "\n")
                    QApplication.clipboard().setText(text_sel)
                    return
                self.pty.write("\x03")
                return
            if key == Qt.Key.Key_V:
                clip = QApplication.clipboard().text()
                if clip:
                    clip = clip.replace("\r\n", "\r").replace("\n", "\r")
                    self.pty.write(clip)
                return
            if Qt.Key.Key_A.value <= key <= Qt.Key.Key_Z.value:
                self.pty.write(chr(key - Qt.Key.Key_A.value + 1))
                return

        specials = {
            Qt.Key.Key_Return:   "\r",
            Qt.Key.Key_Enter:    "\r",
            Qt.Key.Key_Backspace:"\x7f",
            Qt.Key.Key_Tab:      "\t",
            Qt.Key.Key_Escape:   "\x1b",
            Qt.Key.Key_Up:       "\x1b[A",
            Qt.Key.Key_Down:     "\x1b[B",
            Qt.Key.Key_Right:    "\x1b[C",
            Qt.Key.Key_Left:     "\x1b[D",
            Qt.Key.Key_Home:     "\x1b[H",
            Qt.Key.Key_End:      "\x1b[F",
            Qt.Key.Key_PageUp:   "\x1b[5~",
            Qt.Key.Key_PageDown: "\x1b[6~",
            Qt.Key.Key_Delete:   "\x1b[3~",
        }
        if key in specials:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not self.activity:
                    self.activity = "executando..."
                    self.activity_changed.emit(self.activity)
            self.pty.write(specials[key])
            return

        if text:
            self.pty.write(text)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if event.angleDelta().y() > 0:
                self.screen.prev_page()
            else:
                self.screen.next_page()
            self._render()
            event.accept()
            return
        super().wheelEvent(event)
        event.accept()

    def send(self, cmd):
        if self.pty and self.alive:
            try:
                self.activity = cmd[:50] + ("..." if len(cmd) > 50 else "")
                self.activity_changed.emit(self.activity)
                self.pty.write(cmd + "\r")
            except Exception:
                pass

    def font_up(self):
        self._font_size = min(self._font_size + 1, 24)
        self._apply_font()

    def font_down(self):
        self._font_size = max(self._font_size - 1, 6)
        self._apply_font()

    def _apply_font(self):
        font = QFont("Cascadia Mono", self._font_size)
        if not font.exactMatch():
            font = QFont("Consolas", self._font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        QTimer.singleShot(0, self._schedule_resize)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_resize()

    def _schedule_resize(self):
        fm = self.fontMetrics()
        char_w = fm.averageCharWidth()
        char_h = fm.lineSpacing()
        if char_w <= 0 or char_h <= 0:
            return
        margins = self.contentsMargins()
        sb = self.verticalScrollBar()
        scrollbar_w = sb.sizeHint().width() if sb.isVisible() else 0
        avail_w = max(1, self.width() - margins.left() - margins.right() - scrollbar_w)
        avail_h = max(1, self.height() - margins.top() - margins.bottom())
        self._pending_cols = max(10, avail_w // char_w)
        self._pending_rows = max(5,  avail_h // char_h)
        self._resize_timer.start()

    def _do_resize(self):
        new_cols = self._pending_cols
        new_rows = self._pending_rows
        if new_cols == self.screen.columns and new_rows == self.screen.lines:
            return
        # 1. Notificar ConPTY PRIMEIRO — garante que novos dados cheguem já no novo tamanho
        if self.pty and self.alive:
            try:
                self.pty.setwinsize(new_rows, new_cols)
            except Exception:
                pass
        # 2. Recriar tela do pyte
        self.screen = _HistoryScreen(new_cols, new_rows, history=self.HISTORY, ratio=0.5)
        self.stream = pyte.Stream(self.screen)
        # 3. Re-alimentar o buffer bruto
        if self._raw_buf:
            self.stream.feed(self._raw_buf)
            # Clamp do cursor para não estourar nova dimensão
            self.screen.cursor.x = min(self.screen.cursor.x, new_cols - 1)
            self.screen.cursor.y = min(self.screen.cursor.y, new_rows - 1)
        self._render_dirty = True
        self._render()

    def shutdown(self):
        self.alive = False
        if self.pty:
            try:
                self.pty.terminate(force=True)
            except Exception:
                pass

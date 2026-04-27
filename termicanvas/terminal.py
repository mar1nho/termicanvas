"""TerminalWidget + PtyBridge: terminal PyQt com PTY (ConPTY via pywinpty) e pyte."""

import os
import re
import threading

import pyte
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal


class _HistoryScreen(pyte.HistoryScreen):
    def select_graphic_rendition(self, *attrs, private=False, **kwargs):
        super().select_graphic_rendition(*attrs)
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QApplication, QTextEdit

from . import agents
from .config import DEFAULT_CWD
from .tokens import ACCENT, BG_TERMINAL, BORDER, BORDER_HOVER, TEXT_PRIMARY

try:
    from winpty import PtyProcess
    PTY_OK = True
except ImportError:
    PTY_OK = False

PS_PROMPT_RE = re.compile(r"PS\s+[A-Za-z]:\\[^>]*>\s*$")

ANSI_COLORS = {
    "black":         "#000000",
    "red":           "#cd3131",
    "green":         "#0dbc79",
    "yellow":        "#e5e510",
    "blue":          "#2472c8",
    "magenta":       "#bc3fbc",
    "cyan":          "#11a8cd",
    "white":         "#e5e5e5",
    "brightblack":   "#666666",
    "brightred":     "#f14c4c",
    "brightgreen":   "#23d18b",
    "brightyellow":  "#f5f543",
    "brightblue":    "#3b8eea",
    "brightmagenta": "#d670d6",
    "brightcyan":    "#29b8db",
    "brightwhite":   "#ffffff",
    "default":       TEXT_PRIMARY,
}

_BASE_COLOR_NAMES = {"black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"}


# Linhas que NUNCA devem ir pra resposta automatica do agente —
# sao chrome de TUIs (claude code statusline, separadores, prompts vazios).
_CHROME_KEYWORDS = (
    "Session ", "Weekly ", "Sonnet ", "Opus ", "Haiku ", "Context ",
    "Concocting", "Tip:", "thought for", "tokens", "↓", "↑", "✶",
    "claude.de/desktop", "Run Claude Code", "shift+tab",
)
_BOX_DRAWING = set("─━┓┛┃║╔╗╚╝╦╠╣╬│┴┬┼├┤┌┐└┘═")


def _is_chrome_line(line):
    s = line.strip()
    if not s:
        return True
    # box-drawing puro (separadores)
    visible = [c for c in s if not c.isspace()]
    if visible and all(c in _BOX_DRAWING for c in visible):
        return True
    # statusline / dicas / overlays do claude code
    if any(kw in s for kw in _CHROME_KEYWORDS):
        return True
    # prompt vazio
    if s in ("❯", ">", "▏"):
        return True
    return False


def _clean_tui_response(raw):
    """Filtra chrome de TUI (statusline, separadores) e o eco da injecao.

    Pega so o miolo da resposta do agente e limita o tamanho pra nao inundar
    o emissor.
    """
    if not raw:
        return ""
    lines = raw.splitlines()
    cleaned = []
    for line in lines:
        if _is_chrome_line(line):
            continue
        stripped = line.strip()
        # eco da mensagem injetada (ex: "[de: Lider] ...") — pular
        if stripped.startswith("[de:"):
            continue
        # bullet do claude (●) opcional — remove pra resposta limpa
        if stripped.startswith("●"):
            stripped = stripped.lstrip("● ").strip()
        if stripped:
            cleaned.append(stripped)

    response = "\n".join(cleaned).strip()
    # cap em 2000 chars
    if len(response) > 2000:
        response = response[:1997] + "..."
    # se ficou trivial demais, ignora
    if len(response) < 3:
        return ""
    return response


class PtyBridge(QObject):
    data_received = pyqtSignal(str)


class TerminalWidget(QTextEdit):
    activity_changed = pyqtSignal(str)

    COLS      = 100
    ROWS      = 30
    HISTORY   = 1000
    RAW_LIMIT = 100_000  # chars — janela deslizante do stream bruto para re-feed no resize

    def __init__(
        self,
        shell="powershell.exe",
        cwd=None,
        startup_command=None,
        agent_kind=None,
        role_name=None,
        manifest_mode="existing",
        env_extra=None,
        node_id=None,
    ):
        super().__init__()
        self.shell    = shell
        self.cwd      = cwd
        self.activity = ""
        self.agent_kind   = agent_kind
        self.role_name    = role_name
        self.manifest_mode = manifest_mode
        self.node_id      = node_id
        self.env_extra    = env_extra
        # Auto-responder: quando True, depois de receber via bus + idle, captura
        # texto novo no terminal e envia de volta ao emissor via bus.
        self.auto_reply         = False
        self._pending_reply_to  = None  # node_id do emissor da ultima mensagem
        self._reply_baseline    = ""    # _last_content snapshot ANTES da injecao
        self._bus_ref           = None  # injetado pelo main.py apos registrar
        self._startup_command = startup_command
        # CLI do agente sobe via prompt do shell — _check_idle dispara quando PS estiver pronto
        if agent_kind:
            self._startup_command = agents.startup_command(agent_kind)
        self._startup_sent    = False
        self._font_size = 10

        font = QFont()
        font.setFamilies(["Cascadia Mono", "Consolas", "Courier New"])
        font.setPointSize(self._font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        self.setStyleSheet(f"""
            QTextEdit {{
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
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setCursorWidth(2)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Detecta scroll manual pra alternar _auto_scroll. Mudanca programatica
        # (durante _render) e suprimida via _programmatic_scroll flag.
        self.verticalScrollBar().valueChanged.connect(self._on_scrollbar_changed)

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

        # Estado de scroll: True = segue auto pro fundo. Vira False quando o
        # user rola pra cima manualmente (wheel/scrollbar drag), e volta True
        # quando user rola de volta pro fim. Substitui o at_bottom recalculado
        # a cada frame, que era fragil (uma frame errada lockava a posicao).
        self._auto_scroll          = True
        self._programmatic_scroll  = False  # suprime detecao durante setValue interno

        self._render_dirty = False
        self._last_content = ""
        self._render_timer = QTimer(self)
        # 100ms = 10fps. Suave o suficiente pra terminal e -20% rebuilds vs 80ms
        # (rebuild colorido do documento e caro com TUI animado tipo claude code).
        self._render_timer.setInterval(100)
        self._render_timer.timeout.connect(self._flush_render)
        self._render_timer.start()

        # Detector de "stream silencioso" — quando para de chegar dado por X ms,
        # consideramos o shell pronto e disparamos o startup_command (CLI do agente).
        # Mais robusto que regex de prompt (funciona com Oh My Posh, Starship, etc).
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(900)
        self._idle_timer.timeout.connect(self._fire_startup)

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

            if self.agent_kind and target_cwd:
                agents.install_role(
                    target_cwd, self.agent_kind, self.role_name,
                    mode=self.manifest_mode, node_id=self.node_id,
                )

            if self.env_extra:
                env_dict = dict(os.environ)
                env_dict.update(self.env_extra)
                spawn_kwargs["env"] = env_dict

            self.pty   = PtyProcess.spawn(self.shell, **spawn_kwargs)
            self.alive = True
            threading.Thread(target=self._read_loop, daemon=True).start()
        except Exception as e:
            from .diagnostics import record_error
            record_error("terminal._spawn", e)
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
                from .diagnostics import record_error
                record_error("terminal._read_loop", e)
                self.bridge.data_received.emit(f"\n[erro] {e}\n")
                break
        self.alive = False

    def _on_data(self, text):
        self._raw_buf = (self._raw_buf + text)[-self.RAW_LIMIT:]
        self.stream.feed(text)
        self._render_dirty = True
        self._check_idle()
        # Stream chegando = nao esta idle. Reseta o timer de silencio.
        self._idle_timer.start()
        # Se nao havia atividade marcada, sinaliza "tem coisa rolando" pro bus/UI
        if not self.activity:
            self.activity = "..."
            self.activity_changed.emit(self.activity)

    def _fire_startup(self):
        """Callback do timer de silencio (900ms sem dados novos).

        Tres estagios:
        1. Sobe a CLI do agente na primeira vez. Quando agent_kind, prefixa `cls`
           pra limpar o welcome banner do shell antes do TUI do claude/gemini.
        2. Marca como idle pra que o bus possa entregar mensagens.
        3. Auto_reply: se pending_reply_to + bus_ref, captura resposta e envia
           de volta ao emissor.
        """
        if not self.alive:
            return

        # Stage 1: sobe CLI do agente (com cls antes pra limpar o shell)
        if self._startup_command and not self._startup_sent:
            self._startup_sent = True
            cmd = (
                f"cls; {self._startup_command}"
                if self.agent_kind else self._startup_command
            )
            self.send(cmd)
            return

        # Stage 2: marca idle
        if self.activity:
            self.activity = ""
            self.activity_changed.emit("")

        # Stage 3: auto-responder
        if self._pending_reply_to and self._bus_ref:
            self._dispatch_reply()

    def _dispatch_reply(self):
        """Captura texto novo desde a injecao, filtra chrome do TUI e envia."""
        try:
            current = self._last_content
            baseline = self._reply_baseline or ""
            if current.startswith(baseline):
                new_text = current[len(baseline):]
            else:
                new_text = "\n".join(current.splitlines()[-30:])

            response = _clean_tui_response(new_text)
            if response and self._bus_ref:
                self._bus_ref.enqueue(self.node_id, self._pending_reply_to, response)
        except Exception as e:
            from .diagnostics import record_error
            record_error("terminal._dispatch_reply", e)
        finally:
            self._pending_reply_to = None
            self._reply_baseline   = ""

    def set_auto_reply(self, enabled):
        self.auto_reply = bool(enabled)
        if not self.auto_reply:
            self._pending_reply_to = None
            self._reply_baseline   = ""

    def _flush_render(self):
        if self._render_dirty:
            self._render_dirty = False
            from time import perf_counter
            from .diagnostics import record_render_time
            _t0 = perf_counter()
            self._render()
            _elapsed_ms = (perf_counter() - _t0) * 1000
            if _elapsed_ms > 0.1:
                record_render_time(_elapsed_ms)

    def _row_to_str(self, row, width):
        return "".join(row[x].data for x in range(width)).rstrip()

    def _row_to_runs(self, row, width):
        """Converte uma row do pyte em [(text, fg_hex), ...] agrupando por cor."""
        runs = []
        current_text = []
        current_fg = None
        for x in range(width):
            try:
                cell = row[x]
            except (IndexError, KeyError):
                ch = " "
                fg_name = "default"
                bold = False
            else:
                ch = cell.data or " "
                fg_name = (cell.fg or "default")
                bold = bool(getattr(cell, "bold", False))
            fg_hex = ANSI_COLORS.get(fg_name)
            if fg_hex is None:
                # cores diretas (hex sem #) que pyte às vezes devolve
                if isinstance(fg_name, str) and len(fg_name) == 6:
                    try:
                        int(fg_name, 16)
                        fg_hex = "#" + fg_name
                    except ValueError:
                        fg_hex = ANSI_COLORS["default"]
                else:
                    fg_hex = ANSI_COLORS["default"]
            if bold and fg_name in _BASE_COLOR_NAMES:
                fg_hex = ANSI_COLORS.get(f"bright{fg_name}", fg_hex)
            if fg_hex != current_fg:
                if current_text:
                    runs.append(("".join(current_text), current_fg))
                current_text = []
                current_fg = fg_hex
            current_text.append(ch)
        if current_text:
            runs.append(("".join(current_text), current_fg))
        # Trim trailing whitespace-only runs (mantém visual igual ao rstrip antigo)
        while runs and runs[-1][0].rstrip() == "":
            runs.pop()
        return runs

    def _on_scrollbar_changed(self, value):
        """Detecta scroll manual do user pra alternar _auto_scroll.

        - User rola ate o fim -> _auto_scroll = True (retoma auto-follow)
        - User rola pra cima  -> _auto_scroll = False (preserva posicao)
        - Mudancas programaticas (durante _render) sao ignoradas via flag.
        """
        if self._programmatic_scroll:
            return
        sb = self.verticalScrollBar()
        self._auto_scroll = (value >= sb.maximum() - 4)

    def _render(self):
        history_top    = list(self.screen.history.top)
        history_bottom = list(self.screen.history.bottom)

        all_rows = []  # list[list[(text, fg_hex)]]
        for r in history_top:
            all_rows.append(self._row_to_runs(r, self.screen.columns))
        for r in history_bottom:
            all_rows.append(self._row_to_runs(r, self.screen.columns))

        history_count = len(all_rows)

        for y in range(self.screen.lines):
            all_rows.append(self._row_to_runs(self.screen.buffer[y], self.screen.columns))

        # Trim trailing empty rows
        while all_rows and not all_rows[-1]:
            all_rows.pop()

        plain_lines = [
            "".join(text for text, _fg in runs).rstrip()
            for runs in all_rows
        ]
        plain_content = "\n".join(plain_lines)

        if plain_content == self._last_content:
            # Sem mudanca de texto — nao mexe em scroll/cursor.
            return

        # Snapshot ANTES do rebuild. Distancia do fundo preserva exatamente
        # quantas linhas o user ve acima do bottom (mais robusto que ratio).
        sb = self.verticalScrollBar()
        old_scroll = sb.value()
        old_max    = max(1, sb.maximum())
        distance_from_bottom = max(0, old_max - old_scroll)

        self._last_content = plain_content
        # Suprime _on_scrollbar_changed durante o rebuild (clear/insert mexem
        # no scroll varias vezes — sem isso o user_scrolled vira False e trava
        # o auto-follow pra sempre).
        self._programmatic_scroll = True
        try:
            self.setUpdatesEnabled(False)
            try:
                self.clear()
                cursor = self.textCursor()
                cursor.beginEditBlock()
                default_fg = ANSI_COLORS["default"]
                for i, runs in enumerate(all_rows):
                    for text, fg in runs:
                        fmt = QTextCharFormat()
                        fmt.setForeground(QColor(fg or default_fg))
                        cursor.insertText(text, fmt)
                    if i < len(all_rows) - 1:
                        cursor.insertBlock()
                cursor.endEditBlock()
            finally:
                self.setUpdatesEnabled(True)

            if self._auto_scroll:
                # API oficial Qt pra rolar pro fim — lida com lazy maximum
                # corretamente. NAO usar setPosition(meio) + setValue(max),
                # que fazia o widget rolar pra cursor no meio do documento.
                cur = self.textCursor()
                cur.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cur)
                self.ensureCursorVisible()
            else:
                # User rolou pra cima — preserva distancia ate o fundo
                new_max = sb.maximum()
                sb.setValue(max(0, new_max - distance_from_bottom))
        finally:
            self._programmatic_scroll = False

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
            # Startup do agente fica EXCLUSIVAMENTE no _fire_startup (com cls antes
            # do claude/gemini) — evita rodar sem cls quando o regex casa rapido.

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
            except Exception as e:
                from .diagnostics import record_error
                record_error("terminal.send", e)

    def inject_message(self, message, from_node_id=None, from_name=None):
        """Injeta mensagem no PTY como se digitada, separando texto e Enter.

        TUIs como o claude code processam \\r imediatamente quando vem no mesmo
        buffer que o texto — resultado: linha quebrada antes de submeter.
        Dividindo em dois writes com delay garante que o TUI veja a mensagem
        completa primeiro e SO ENTAO o Enter como submit.

        Se from_name veio, prefixa "[de: <nome>] " pra destinatario identificar
        emissor. Se auto_reply ativo, registra pending_reply_to + baseline.
        """
        if not (self.pty and self.alive):
            return

        if from_name:
            text = f"[de: {from_name}] {message}"
        else:
            text = message

        if self.auto_reply and from_node_id:
            self._pending_reply_to = from_node_id
            self._reply_baseline   = self._last_content

        try:
            self.activity = (text[:50] + "...") if len(text) > 50 else text
            self.activity_changed.emit(self.activity)
            self.pty.write(text)
        except Exception as e:
            from .diagnostics import record_error
            record_error("terminal.inject_message", e)
            return

        # Enter separado apos delay — deixa o TUI processar a linha completa
        QTimer.singleShot(150, self._inject_enter)

    def _inject_enter(self):
        if self.pty and self.alive:
            try:
                self.pty.write("\r")
            except Exception as e:
                from .diagnostics import record_error
                record_error("terminal._inject_enter", e)

    def font_up(self):
        self._font_size = min(self._font_size + 1, 24)
        self._apply_font()

    def font_down(self):
        self._font_size = max(self._font_size - 1, 6)
        self._apply_font()

    def _apply_font(self):
        font = QFont()
        font.setFamilies(["Cascadia Mono", "Consolas", "Courier New"])
        font.setPointSize(self._font_size)
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
        self._render_timer.stop()
        self._idle_timer.stop()
        self._resize_timer.stop()
        if self.pty:
            try:
                self.pty.terminate(force=True)
            except Exception:
                pass
        self.deleteLater()

"""
TermiCanvas — Orchestration Canvas
----------------------------------
Entry point. Composicao das pecas do pacote `termicanvas`.
"""

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QVBoxLayout, QWidget

from termicanvas.agent import AgentWidget
from termicanvas.canvas import CanvasView
from termicanvas.config import DEFAULT_CWD, set_last_custom_cwd
from termicanvas.dialogs import TerminalLaunchDialog
from termicanvas.session import load_session, save_session
from termicanvas.terminal import TerminalWidget
from termicanvas.tokens import ACCENT, BG_CANVAS
from termicanvas.topbar import TopBar
from termicanvas.widgets import NoteWidget, PromptCard


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TermiCanvas")
        self.resize(1520, 960)
        self.setStyleSheet(f"QMainWindow {{ background: {BG_CANVAS}; }}")

        self.canvas = CanvasView()

        self.topbar = TopBar()
        self.topbar.add_terminal.connect(self._add_term)
        self.topbar.add_note.connect(self._add_note)
        self.topbar.add_agent.connect(self._add_agent)
        self.topbar.add_prompt.connect(self._add_prompt)
        self.topbar.accent_changed.connect(self._on_accent_changed)
        self.topbar.terminals_bar.terminal_clicked.connect(self.canvas.focus_and_center)

        self.canvas.nodes_changed.connect(self._refresh_terminals_bar)
        self.canvas.new_terminal_requested.connect(lambda: self._add_term("powershell.exe"))

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.topbar)
        central_layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        self.last_terminal     = None
        self._terminal_counter = 0

        QTimer.singleShot(0, self._load_session)

    def _load_session(self):
        data = load_session()
        if not data:
            return

        for node in data.get("nodes", []):
            ntype = node.get("type")
            name  = node.get("name", "Terminal")
            x, y  = node.get("x", 0.0), node.get("y", 0.0)
            w, h  = node.get("w", 720), node.get("h", 460)
            color = node.get("color", ACCENT)
            custom = node.get("custom_color", False)

            if ntype == "terminal":
                shell     = node.get("shell", "powershell.exe")
                cwd       = node.get("cwd", DEFAULT_CWD)
                font_size = node.get("font_size", 10)

                t = TerminalWidget(shell=shell, cwd=cwd)
                t._font_size = font_size

                frame = self.canvas.add_node(t, name, size=(w, h))
                t._apply_font()
                frame.set_node_color(color, custom=custom)
                self.last_terminal = t
                self._terminal_counter += 1
                t.activity_changed.connect(lambda _: self._refresh_terminals_bar())

            elif ntype == "note":
                content = node.get("content", "")
                n = NoteWidget()
                n.setPlainText(content)
                frame = self.canvas.add_node(n, name, size=(w, h))

            elif ntype == "agent":
                a = AgentWidget()
                frame = self.canvas.add_node(a, name, size=(w, h))
                a.route_output.connect(lambda text, f=frame: self._route_output(f, text))

            elif ntype == "prompt":
                p = PromptCard()
                p.setText(node.get("content", ""))
                frame = self.canvas.add_node(p, name, size=(w, h))
                p.route_output.connect(lambda text, f=frame: self._route_output(f, text))

            else:
                continue

            for proxy, f in self.canvas.proxies:
                if f is frame:
                    proxy.setPos(x, y)
                    break

        cs = data.get("canvas", {})
        scale    = cs.get("scale", 1.0)
        scroll_h = cs.get("scroll_h", 0)
        scroll_v = cs.get("scroll_v", 0)
        accent   = cs.get("accent_color", ACCENT)

        self.canvas.resetTransform()
        if abs(scale - 1.0) > 0.001:
            self.canvas.scale(scale, scale)
        self.canvas.horizontalScrollBar().setValue(scroll_h)
        self.canvas.verticalScrollBar().setValue(scroll_v)

        if accent != ACCENT:
            self.topbar._accent_color = accent
            self.topbar._update_swatch()
            self._on_accent_changed(accent)

        frame_list = [f for _, f in self.canvas.proxies]
        for src_idx, tgt_idx in data.get("connections", []):
            if 0 <= src_idx < len(frame_list) and 0 <= tgt_idx < len(frame_list):
                self.canvas.connections.append((frame_list[src_idx], frame_list[tgt_idx]))

        self._refresh_terminals_bar()

    def _refresh_terminals_bar(self):
        self.topbar.terminals_bar.sync(self.canvas)

    def _on_accent_changed(self, color):
        for proxy, frame in self.canvas.proxies:
            if not frame._custom_color:
                frame.set_node_color(color)
        for chip in self.topbar.terminals_bar.chips.values():
            if not chip._custom_accent:
                chip.set_accent(color)

    def _add_term(self, shell):
        pretty_shell = {
            "powershell.exe": "PowerShell",
            "pwsh.exe":       "PowerShell 7",
            "cmd.exe":        "CMD",
        }.get(shell, shell)

        default_name = f"{pretty_shell} {self._terminal_counter + 1}"
        dialog = TerminalLaunchDialog(pretty_shell, default_name=default_name, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cwd         = dialog.chosen_cwd()
        chosen_name = dialog.chosen_name()

        if cwd and cwd != DEFAULT_CWD:
            set_last_custom_cwd(cwd)

        self._terminal_counter += 1
        t     = TerminalWidget(shell=shell, cwd=cwd)
        frame = self.canvas.add_node(t, chosen_name, size=(720, 460))
        self.last_terminal = t
        t.activity_changed.connect(lambda _: self._refresh_terminals_bar())

    def _add_note(self):
        n = NoteWidget()
        self.canvas.add_node(n, "Nota", size=(340, 280))

    def _add_agent(self):
        a = AgentWidget()
        frame = self.canvas.add_node(a, "Agent", size=(480, 580))
        a.route_output.connect(lambda text, f=frame: self._route_output(f, text))

    def _add_prompt(self):
        p = PromptCard()
        frame = self.canvas.add_node(p, "Prompt", size=(420, 280))
        p.route_output.connect(lambda text, f=frame: self._route_output(f, text))

    def _route_output(self, source_frame, text):
        for src, tgt in self.canvas.connections:
            if src is source_frame:
                if isinstance(tgt.inner, AgentWidget):
                    tgt.inner.receive(text)
                elif isinstance(tgt.inner, TerminalWidget):
                    tgt.inner.send(text)
                break

    def closeEvent(self, e):
        save_session(self.canvas, self.topbar._accent_color)
        for proxy, frame in self.canvas.proxies:
            if isinstance(frame.inner, TerminalWidget):
                frame.inner.shutdown()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""
TermiCanvas — Orchestration Canvas
----------------------------------
Entry point. Composicao das pecas do pacote `termicanvas`.
"""

import os
import sys
import uuid

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from termicanvas._debug import snapshot
from termicanvas.agent import AgentWidget
from termicanvas.agents import AGENT_KINDS, managed_manifest_path
from termicanvas.bus import Bus
from termicanvas.canvas import CanvasView
from termicanvas.config import DEFAULT_CWD, ensure_dirs, set_last_custom_cwd
from termicanvas.dialogs import RoleEditorDialog, TerminalLaunchDialog
from termicanvas.roles import seed_roles
from termicanvas.session import load_session, save_session
from termicanvas.sidebar import TerminalsSidebar
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

        ensure_dirs()
        seed_roles()

        self.canvas  = CanvasView()
        self.bus     = Bus()
        self.bus.start(self.canvas)
        self.canvas._bus_ref = self.bus
        self.sidebar = TerminalsSidebar()

        self.topbar = TopBar()
        self.topbar.add_terminal.connect(lambda shell: self._add_term(shell))
        self.topbar.add_agent_terminal.connect(self._add_agent_terminal)
        self.topbar.add_note.connect(self._add_note)
        self.topbar.add_agent.connect(self._add_agent)
        self.topbar.add_prompt.connect(self._add_prompt)
        self.topbar.accent_changed.connect(self._on_accent_changed)
        self.topbar.toggle_sidebar.connect(self.sidebar.toggle)
        self.sidebar.terminal_clicked.connect(self.canvas.focus_and_center)

        self.canvas.nodes_changed.connect(self._refresh_sidebar)
        self.canvas.new_terminal_requested.connect(lambda: self._add_term("powershell.exe"))

        # Layout: topbar em cima; abaixo, sidebar (esquerda) + canvas (direita)
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.topbar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.canvas, 1)
        root.addWidget(body, 1)

        self.setCentralWidget(central)

        self.last_terminal     = None
        self._terminal_counter = 0

        QTimer.singleShot(0, self._load_session)

        snapshot("init", self.bus)

    # ---------- session restore ----------

    def _load_session(self):
        data = load_session()
        if not data:
            return

        for node in data.get("nodes", []):
            ntype = node.get("type")
            name  = node.get("name", "Terminal")
            icon  = node.get("icon", "")
            x, y  = node.get("x", 0.0), node.get("y", 0.0)
            w, h  = node.get("w", 720), node.get("h", 460)
            color = node.get("color", ACCENT)
            custom = node.get("custom_color", False)

            if ntype == "terminal":
                shell         = node.get("shell", "powershell.exe")
                cwd           = node.get("cwd", DEFAULT_CWD)
                font_size     = node.get("font_size", 10)
                agent_kind    = node.get("agent_kind")
                role_name     = node.get("role_name")
                manifest_mode = node.get("manifest_mode", "existing")
                auto_reply    = node.get("auto_reply", False)

                self._terminal_counter += 1
                t = self._make_terminal(
                    shell=shell, cwd=cwd,
                    agent_kind=agent_kind, role_name=role_name,
                    manifest_mode=manifest_mode,
                )
                t._font_size = font_size
                t.auto_reply = auto_reply

                frame = self.canvas.add_node(t, name, size=(w, h), icon=icon)
                self._register_terminal(t, frame, name)
                self._wire_role_editor(t, frame)
                self._wire_agent_controls(t, frame)
                frame.header.title_changed.connect(
                    lambda title, tid=t.node_id: self.bus.update_name(tid, title)
                )
                t._apply_font()
                frame.set_node_color(color, custom=custom)
                self.last_terminal = t
                t.activity_changed.connect(lambda _: self._refresh_sidebar())

            elif ntype == "note":
                content = node.get("content", "")
                n = NoteWidget()
                n.setPlainText(content)
                frame = self.canvas.add_node(n, name, size=(w, h), icon=icon)

            elif ntype == "agent":
                a = AgentWidget()
                frame = self.canvas.add_node(a, name, size=(w, h), icon=icon)
                a.route_output.connect(lambda text, f=frame: self._route_output(f, text))

            elif ntype == "prompt":
                p = PromptCard()
                p.setText(node.get("content", ""))
                frame = self.canvas.add_node(p, name, size=(w, h), icon=icon)
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

        self._refresh_sidebar()

    # ---------- helpers ----------

    def _refresh_sidebar(self):
        self.sidebar.sync(self.canvas)

    def _on_accent_changed(self, color):
        for proxy, frame in self.canvas.proxies:
            if not frame._custom_color:
                frame.set_node_color(color)
        for chip in self.sidebar.chips.values():
            if not chip._custom_accent:
                chip.set_accent(color)
        self.canvas._nav.set_accent(color)

    def _make_terminal(self, shell, cwd, agent_kind=None, role_name=None, manifest_mode="existing"):
        """Cria TerminalWidget com env_extra contendo URL do bus + node_id reservado."""
        reserved_id = uuid.uuid4().hex[:12]
        env_extra = {}
        if self.bus.url():
            env_extra["TERMICANVAS_BUS_URL"] = self.bus.url()
        env_extra["TERMICANVAS_NODE_ID"] = reserved_id
        # Adiciona o projeto ao PYTHONPATH pro agente conseguir rodar `python -m termicanvas.cli`
        project_root = os.path.dirname(os.path.abspath(__file__))
        existing_pp = os.environ.get("PYTHONPATH", "")
        if existing_pp:
            env_extra["PYTHONPATH"] = f"{project_root}{os.pathsep}{existing_pp}"
        else:
            env_extra["PYTHONPATH"] = project_root

        t = TerminalWidget(
            shell=shell, cwd=cwd,
            agent_kind=agent_kind, role_name=role_name,
            manifest_mode=manifest_mode,
            env_extra=env_extra, node_id=reserved_id,
        )
        return t

    def _register_terminal(self, terminal, frame, name):
        """Registra terminal no bus usando o node_id reservado em _make_terminal."""
        self.bus.register_with_id(
            terminal.node_id, terminal, frame, name, agent_kind=terminal.agent_kind,
        )

    def _wire_role_editor(self, terminal, frame):
        """Habilita botao 'editar role' no header se for agente em modo managed."""
        if not (terminal.agent_kind and terminal.manifest_mode == "managed" and terminal.cwd):
            return
        frame.header.show_role_btn()
        frame.header.edit_role_clicked.connect(
            lambda t=terminal: self._open_role_editor(t)
        )

    def _wire_agent_controls(self, terminal, frame):
        """Habilita botao auto-responder + injeta bus_ref pro reply funcionar."""
        if not terminal.agent_kind:
            return
        terminal._bus_ref = self.bus
        frame.header.show_auto_reply_btn()
        frame.header.set_auto_reply_state(terminal.auto_reply)
        frame.header.auto_reply_toggled.connect(terminal.set_auto_reply)

    def _open_role_editor(self, terminal):
        if not terminal.cwd or not terminal.agent_kind:
            return
        path = managed_manifest_path(terminal.cwd, terminal.agent_kind)
        if path is None:
            return
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Role livre\n\nResponda em portugues, de forma direta.\n", encoding="utf-8")
        dlg = RoleEditorDialog(path, parent=self)
        dlg.exec()

    # ---------- adicionadores ----------

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
        chosen_icon = dialog.chosen_icon()

        if cwd and cwd != DEFAULT_CWD:
            set_last_custom_cwd(cwd)

        self._terminal_counter += 1
        t     = self._make_terminal(shell=shell, cwd=cwd)
        frame = self.canvas.add_node(t, chosen_name, size=(720, 460), icon=chosen_icon)
        self._register_terminal(t, frame, chosen_name)
        frame.header.title_changed.connect(
            lambda title, tid=t.node_id: self.bus.update_name(tid, title)
        )
        self.last_terminal = t
        t.activity_changed.connect(lambda _: self._refresh_sidebar())

    def _add_agent_terminal(self, agent_kind):
        if agent_kind not in AGENT_KINDS:
            return
        spec  = AGENT_KINDS[agent_kind]
        label = spec["label"]

        default_name = f"{label} {self._terminal_counter + 1}"
        dialog = TerminalLaunchDialog(
            label, default_name=default_name, parent=self, agent_kind=agent_kind,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        cwd         = dialog.chosen_cwd()
        chosen_name = dialog.chosen_name()
        chosen_icon = dialog.chosen_icon()
        chosen_role = dialog.chosen_role()
        chosen_mode = dialog.chosen_manifest_mode()

        if cwd and cwd != DEFAULT_CWD:
            set_last_custom_cwd(cwd)

        self._terminal_counter += 1
        t     = self._make_terminal(
            shell="powershell.exe", cwd=cwd,
            agent_kind=agent_kind, role_name=chosen_role,
            manifest_mode=chosen_mode,
        )
        frame = self.canvas.add_node(t, chosen_name, size=(820, 540), icon=chosen_icon)
        self._register_terminal(t, frame, chosen_name)
        self._wire_role_editor(t, frame)
        self._wire_agent_controls(t, frame)
        frame.header.title_changed.connect(
            lambda title, tid=t.node_id: self.bus.update_name(tid, title)
        )
        self.last_terminal = t
        t.activity_changed.connect(lambda _: self._refresh_sidebar())

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
        try:
            self.bus.stop()
        except Exception:
            pass
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

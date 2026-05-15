"""NodeFactory — API única pra criar qualquer node no canvas.

Substitui os 6 métodos _add_* espalhados em main.py. Centraliza:
- mapeamento kind → widget class
- aplicação de geometry (posição + tamanho) ou defaults
- abertura opcional do TerminalLaunchDialog
- singleton handling do Debug Monitor
"""

from typing import Optional

from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QDialog

from .agent import AgentWidget
from .agents import AGENT_KINDS, promote_to_orchestrator
from .config import get_default_cwd, set_last_custom_cwd
from .dialogs import TerminalLaunchDialog
from .preview import PreviewWidget
from .widgets import NoteWidget, PromptCard


# kind → (default_w, default_h)
DEFAULT_SIZES = {
    "powershell": (720, 460),
    "cmd":        (720, 460),
    "claude":     (820, 540),
    "gemini":     (820, 540),
    "codex":      (820, 540),
    "note":       (340, 280),
    "prompt":     (420, 280),
    "agent":      (480, 580),
    "debug":      (560, 600),
    "preview":    (640, 520),
}

# kind → shell binary (só pra terminais reais e agentes)
SHELL_FOR_KIND = {
    "powershell": "powershell.exe",
    "cmd":        "cmd.exe",
    "claude":     "powershell.exe",  # default; dialog permite CMD
    "gemini":     "powershell.exe",
    "codex":      "powershell.exe",
}

# kind → agent_kind (None pra terminais simples)
AGENT_FOR_KIND = {
    "claude": "claude",
    "gemini": "gemini",
    "codex":  "codex",
}


class NodeFactory:
    """Cria nodes no canvas a partir de um `kind` semântico.

    Reaproveita os helpers existentes em MainWindow (_make_terminal,
    _register_terminal, _wire_*) — só centraliza a lógica de qual chamar.
    """

    def __init__(self, main_window):
        self.main = main_window

    def create(
        self,
        kind: str,
        *,
        geometry: Optional[QRectF] = None,
        with_dialog: bool = False,
        cwd: Optional[str] = None,
        name: Optional[str] = None,
        owned_cwd: bool = False,
        shell: Optional[str] = None,
        role_name: Optional[str] = None,
        manifest_mode: Optional[str] = None,
        orchestrator: bool = False,
    ):
        """Cria um node do tipo `kind`.

        Args:
            kind: um de DEFAULT_SIZES.keys()
            geometry: rect em scene coords. Se None, usa fallback do canvas
                      (centro da viewport com offset escalonado).
            with_dialog: se True, abre TerminalLaunchDialog antes (só faz
                         sentido pra kinds com cwd: terminais e agentes).
            cwd: cwd custom (bypass dialog). Usado por /spawn pra criar
                 agentes em pastas pre-preparadas.
            name: nome custom (bypass auto-numbering).

        Returns:
            NodeFrame criado, ou None se kind inválido / dialog cancelado /
            singleton já existe (foca o existente nesse caso).
        """
        if kind not in DEFAULT_SIZES:
            return None

        # Singleton: Debug Monitor
        if kind == "debug":
            from .monitor import DebugMonitorWidget
            for proxy, frame in self.main.canvas.proxies:
                if isinstance(frame.inner, DebugMonitorWidget):
                    self.main.canvas.focus_and_center(frame)
                    return frame

        # Dispatch por categoria
        if kind in ("powershell", "cmd"):
            return self._create_terminal(
                kind, geometry, with_dialog, cwd=cwd, name=name, owned_cwd=owned_cwd,
            )
        if kind in AGENT_FOR_KIND:
            return self._create_agent_terminal(
                kind, geometry, with_dialog, cwd=cwd, name=name, owned_cwd=owned_cwd,
                shell=shell, role_name=role_name, manifest_mode=manifest_mode,
                orchestrator=orchestrator,
            )
        if kind == "note":
            return self._create_simple(kind, NoteWidget(), "Nota", geometry)
        if kind == "prompt":
            card = PromptCard()
            frame = self._create_simple(kind, card, "Prompt", geometry)
            card.route_output.connect(
                lambda text, f=frame: self.main._route_output(f, text)
            )
            return frame
        if kind == "agent":
            agent = AgentWidget()
            frame = self._create_simple(kind, agent, "Agent", geometry)
            agent.route_output.connect(
                lambda text, f=frame: self.main._route_output(f, text)
            )
            return frame
        if kind == "debug":
            from .monitor import DebugMonitorWidget
            widget = DebugMonitorWidget(canvas=self.main.canvas, bus=self.main.bus)
            return self._create_simple(kind, widget, "Debug Monitor", geometry, icon="")
        if kind == "preview":
            return self._create_preview(geometry, with_dialog)
        return None

    # ---------- helpers ----------

    def _resolve_size(self, kind, geometry):
        """Se geometry tem tamanho >= 240x180, usa ele. Senão, default do kind.
        Geometry com width/height = 0 (clique simples sem drag) cai no default."""
        if geometry is not None and geometry.width() >= 240 and geometry.height() >= 180:
            return int(geometry.width()), int(geometry.height())
        return DEFAULT_SIZES[kind]

    def _apply_position(self, frame, geometry):
        """Se geometry foi passado, posiciona o proxy. Senão, deixa o
        canvas.add_node usar o fallback default (centro da viewport)."""
        if geometry is None:
            return
        proxy = next(
            p for p, f in self.main.canvas.proxies if f is frame
        )
        proxy.setPos(geometry.x(), geometry.y())

    def _create_simple(self, kind, widget, default_title, geometry, icon=""):
        w, h = self._resolve_size(kind, geometry)
        frame = self.main.canvas.add_node(widget, default_title, size=(w, h), icon=icon)
        self._apply_position(frame, geometry)
        return frame

    def _create_terminal(self, kind, geometry, with_dialog, cwd=None, name=None, owned_cwd=False):
        shell = SHELL_FOR_KIND[kind]
        pretty = {"powershell": "PowerShell", "cmd": "CMD"}[kind]
        default_name = name or f"{pretty} {self.main._terminal_counter + 1}"

        chosen_cwd  = cwd or get_default_cwd()
        chosen_name = default_name
        chosen_icon = ""

        if with_dialog:
            dlg = TerminalLaunchDialog(pretty, default_name=default_name, parent=self.main)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
            chosen_cwd  = dlg.chosen_cwd()
            chosen_name = dlg.chosen_name()
            chosen_icon = dlg.chosen_icon()
            if chosen_cwd and chosen_cwd != get_default_cwd():
                set_last_custom_cwd(chosen_cwd)

        self.main._terminal_counter += 1
        t = self.main._make_terminal(shell=shell, cwd=chosen_cwd, owned_cwd=owned_cwd)
        w, h = self._resolve_size(kind, geometry)
        frame = self.main.canvas.add_node(t, chosen_name, size=(w, h), icon=chosen_icon)
        self._apply_position(frame, geometry)
        self.main._register_terminal(t, frame, chosen_name)
        frame.header.title_changed.connect(
            lambda title, tid=t.node_id: self.main.bus.update_name(tid, title)
        )
        self.main.last_terminal = t
        t.activity_changed.connect(lambda _: self.main._refresh_sidebar())
        return frame

    def _create_agent_terminal(
        self, kind, geometry, with_dialog, cwd=None, name=None, owned_cwd=False,
        shell=None, role_name=None, manifest_mode=None, orchestrator=False,
    ):
        agent_kind = AGENT_FOR_KIND[kind]
        spec = AGENT_KINDS[agent_kind]
        label = spec["label"]
        default_name = name or f"{label} {self.main._terminal_counter + 1}"

        chosen_cwd  = cwd or get_default_cwd()
        chosen_name = default_name
        chosen_icon = spec.get("icon", "")
        chosen_role = role_name
        chosen_mode = manifest_mode or "existing"
        chosen_orchestrator = bool(orchestrator)
        chosen_shell = shell or SHELL_FOR_KIND[kind]

        if with_dialog:
            dlg = TerminalLaunchDialog(
                label, default_name=default_name, parent=self.main, agent_kind=agent_kind,
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
            chosen_cwd  = dlg.chosen_cwd()
            chosen_name = dlg.chosen_name()
            chosen_icon = dlg.chosen_icon()
            chosen_role = dlg.chosen_role()
            chosen_mode = dlg.chosen_manifest_mode()
            chosen_orchestrator = dlg.chosen_orchestrator()
            chosen_shell = dlg.chosen_shell() or chosen_shell
            if chosen_cwd and chosen_cwd != get_default_cwd():
                set_last_custom_cwd(chosen_cwd)

        # Apende o system prompt de orquestrador no manifesto, se solicitado.
        # Independente do manifest_mode: funciona com manifesto ja existente
        # tambem (apende como bloco delimitado pra ser idempotente).
        if chosen_orchestrator:
            promote_to_orchestrator(chosen_cwd, agent_kind)

        self.main._terminal_counter += 1
        t = self.main._make_terminal(
            shell=chosen_shell, cwd=chosen_cwd,
            agent_kind=agent_kind, role_name=chosen_role,
            manifest_mode=chosen_mode,
            owned_cwd=owned_cwd,
        )
        w, h = self._resolve_size(kind, geometry)
        frame = self.main.canvas.add_node(t, chosen_name, size=(w, h), icon=chosen_icon)
        self._apply_position(frame, geometry)
        self.main._register_terminal(t, frame, chosen_name)
        self.main._wire_role_editor(t, frame)
        self.main._wire_agent_controls(t, frame)
        frame.header.title_changed.connect(
            lambda title, tid=t.node_id: self.main.bus.update_name(tid, title)
        )
        self.main.last_terminal = t
        t.activity_changed.connect(lambda _: self.main._refresh_sidebar())
        return frame

    def _create_preview(self, geometry, with_dialog):
        path = ""
        mode = "auto"
        title = "Preview"
        if with_dialog:
            from .dialogs import PreviewLaunchDialog
            dlg = PreviewLaunchDialog(parent=self.main)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
            path = dlg.chosen_path()
            mode = dlg.chosen_mode()
            if path:
                from pathlib import Path
                title = Path(path).name
        widget = PreviewWidget(path=path, mode=mode)
        return self._create_simple("preview", widget, title, geometry)

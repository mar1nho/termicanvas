"""
TermiCanvas — Orchestration Canvas
----------------------------------
Entry point. Composicao das pecas do pacote `termicanvas`.
"""

import os
import sys
import uuid

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from termicanvas import snapshots as snapshots_mod
from termicanvas.agent import AgentWidget
from termicanvas.agents import AGENT_KINDS, managed_manifest_path
from termicanvas.bus import Bus
from termicanvas.canvas import CanvasView
from termicanvas.config import DEFAULT_CWD, ensure_dirs, set_last_custom_cwd
from termicanvas.dialogs import (
    BusOffConfirmDialog,
    LoadSnapshotConfirmDialog,
    RoleEditorDialog,
    SnapshotNameDialog,
    TerminalLaunchDialog,
)
from termicanvas.diagnostics import record_error
from termicanvas.insert_controller import InsertController, InsertState
from termicanvas.island import ToolIsland
from termicanvas.node_factory import NodeFactory
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

        # Read persisted state BEFORE starting bus / loading nodes.
        data = load_session() or {}
        cs = data.get("canvas", {})
        self._bus_enabled         = bool(cs.get("bus_enabled", False))
        self._bus_toggle_warned   = bool(cs.get("bus_toggle_warned", False))
        self._snapshot_load_warned = bool(cs.get("snapshot_load_warned", False))

        self.canvas  = CanvasView()
        self.bus     = Bus()
        # Spawn dinamico via /spawn — orquestrador cria novos agentes.
        # Signal cross-thread (HTTP -> UI) com QueuedConnection automatica.
        self.bus.spawn_requested.connect(self._on_spawn_requested)
        if self._bus_enabled:
            self.bus.start(self.canvas)
        self.canvas._bus_ref = self.bus
        self.sidebar = TerminalsSidebar()

        self.factory = NodeFactory(self)

        self.topbar = TopBar(parent=self.canvas)
        self.topbar.accent_changed.connect(self._on_accent_changed)
        self.topbar.theme_toggled.connect(self._on_theme_toggled)
        self.sidebar.collapse_toggled.connect(
            lambda _: QTimer.singleShot(0, self._reposition_overlays)
        )
        self.topbar.bus_toggled.connect(self._on_bus_toggled)

        # Tool Island (overlay no canvas) + InsertController (state machine)
        self.island = ToolIsland(parent=self.canvas)
        self._island_manual_position = False
        self.insert = InsertController(parent=self)

        self.island.tool_armed.connect(self.insert.arm)
        self.island.tool_doubled.connect(
            lambda kind: self.factory.create(kind, with_dialog=False)
        )
        self.island.user_moved.connect(self._on_island_user_moved)
        self.canvas.island_center_requested.connect(self._center_island)
        self.insert.armed_kind_changed.connect(self.island.set_armed_kind)
        self.insert.state_changed.connect(self._on_insert_state_changed)
        self.insert.drag_updated.connect(self.canvas.show_drag_preview)
        self.insert.commit_requested.connect(self._on_insert_commit)
        self.canvas.insert_press.connect(self.insert.start_drag)
        self.canvas.insert_move.connect(self.insert.update_drag)
        self.canvas.insert_release.connect(self.insert.finish_drag)
        self.canvas.insert_escape.connect(self.insert.disarm)

        QApplication.instance().installEventFilter(self)
        self.sidebar.terminal_clicked.connect(self.canvas.focus_and_center)
        self.sidebar.snapshot_save_requested.connect(self._on_snapshot_save_requested)
        self.sidebar.snapshot_load_requested.connect(self._on_snapshot_load_requested)
        self.sidebar.snapshot_rename_requested.connect(self._on_snapshot_rename_requested)
        self.sidebar.snapshot_overwrite_requested.connect(self._on_snapshot_overwrite_requested)
        self.sidebar.snapshot_delete_requested.connect(self._on_snapshot_delete_requested)

        self.canvas.nodes_changed.connect(self._refresh_sidebar)
        self.canvas.new_terminal_requested.connect(lambda: self._add_term("powershell.exe"))
        self.canvas.debug_monitor_requested.connect(self._add_debug_monitor)

        # Layout: sidebar (esquerda) + canvas (direita). Controles de topo sao
        # overlays do canvas, nao ocupam espaco no layout.
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

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

        # Reflect the persisted bus state on the topbar.
        self.topbar.set_bus_state(self._bus_enabled)

        # Refresh inicial da sidebar de snapshots.
        self._refresh_snapshots_sidebar()

        # Atalho Ctrl+S para salvar snapshot.
        self._save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self._save_shortcut.activated.connect(self._on_snapshot_save_requested)

        # Defer node restore + viewport apply to next event loop tick so the
        # window is fully constructed first (matches the previous QTimer.singleShot
        # behavior).
        if self._bus_enabled:
            QTimer.singleShot(0, lambda d=data: (
                self._load_session_nodes(d),
                self._apply_session_viewport(d),
            ))
        else:
            QTimer.singleShot(0, lambda d=data: self._apply_session_viewport(d))

    # ---------- session restore ----------

    def _load_session(self):
        data = load_session()
        if not data:
            return
        self._load_session_nodes(data)
        self._apply_session_viewport(data)

    def _load_session_nodes(self, data):
        # Nodes herdam a accent global via canvas.add_node — campos color e
        # custom_color persistidos em sessoes antigas sao ignorados.
        for node in data.get("nodes", []):
            ntype = node.get("type")
            name  = node.get("name", "Terminal")
            icon  = node.get("icon", "")
            x, y  = node.get("x", 0.0), node.get("y", 0.0)
            w, h  = node.get("w", 720), node.get("h", 460)

            if ntype == "terminal":
                shell         = node.get("shell", "powershell.exe")
                cwd           = node.get("cwd", DEFAULT_CWD)
                font_size     = node.get("font_size", 10)
                agent_kind    = node.get("agent_kind")
                role_name     = node.get("role_name")
                manifest_mode = node.get("manifest_mode", "existing")
                # Default agora e True para terminals com agent_kind (orquestrador
                # e agentes spawnados); sessoes antigas que ja salvaram explicitamente
                # False respeitam isso.
                default_auto_reply = bool(agent_kind)
                auto_reply    = node.get("auto_reply", default_auto_reply)

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
                self.last_terminal = t
                t.activity_changed.connect(lambda _: self._refresh_sidebar())

            elif ntype == "note":
                content = node.get("content", "")
                n = NoteWidget()
                n.setPlainText(content)
                self.canvas.add_node(n, name, size=(w, h), icon=icon)

            elif ntype == "agent":
                a = AgentWidget()
                frame = self.canvas.add_node(a, name, size=(w, h), icon=icon)
                a.route_output.connect(lambda text, f=frame: self._route_output(f, text))

            elif ntype == "prompt":
                p = PromptCard()
                p.setText(node.get("content", ""))
                frame = self.canvas.add_node(p, name, size=(w, h), icon=icon)
                p.route_output.connect(lambda text, f=frame: self._route_output(f, text))

            elif ntype == "debug_monitor":
                from termicanvas.monitor import DebugMonitorWidget
                widget = DebugMonitorWidget(canvas=self.canvas, bus=self.bus)
                self.canvas.add_node(widget, name, size=(w, h), icon=icon)

            else:
                continue

            for proxy, f in self.canvas.proxies:
                if f is frame:
                    proxy.setPos(x, y)
                    break

        frame_list = [f for _, f in self.canvas.proxies]
        for src_idx, tgt_idx in data.get("connections", []):
            if 0 <= src_idx < len(frame_list) and 0 <= tgt_idx < len(frame_list):
                self.canvas.connections.append((frame_list[src_idx], frame_list[tgt_idx]))

        self._refresh_sidebar()

    def _apply_session_viewport(self, data):
        cs = data.get("canvas", {})
        scale    = cs.get("scale", 1.0)
        scroll_h = cs.get("scroll_h", 0)
        scroll_v = cs.get("scroll_v", 0)
        accent     = cs.get("accent_color", ACCENT)
        light_mode = cs.get("light_mode", False)

        self.canvas.resetTransform()
        if abs(scale - 1.0) > 0.001:
            self.canvas.scale(scale, scale)
        self.canvas.horizontalScrollBar().setValue(scroll_h)
        self.canvas.verticalScrollBar().setValue(scroll_v)

        # Sempre propaga a accent persistida — _on_accent_changed se encarrega
        # de sincronizar canvas, sidebar e nav (idempotente quando == ACCENT).
        self.topbar._accent_color = accent
        self.topbar._update_swatch()
        self._on_accent_changed(accent)

        # Restaura o tema persistido (light/dark) — sempre propaga, mesmo
        # quando False, para cobrir o caso "snapshot dark sobre sessao light".
        self.topbar.set_light_mode(light_mode)
        self.canvas.set_light_mode(light_mode)
        self.sidebar.set_light_mode(light_mode)
        self.island.set_light_mode(light_mode)

    # ---------- helpers ----------

    def _refresh_sidebar(self):
        self.sidebar.sync(self.canvas)

    def _on_accent_changed(self, color):
        # Sincroniza o canvas pra que nodes futuros nascam com a cor nova.
        self.canvas.set_accent(color)
        for proxy, frame in self.canvas.proxies:
            frame.set_node_color(color)
        for chip in self.sidebar.chips.values():
            chip.set_accent(color)
        self.canvas._nav.set_accent(color)

    def _on_theme_toggled(self, light_mode: bool):
        self.canvas.set_light_mode(light_mode)
        self.sidebar.set_light_mode(light_mode)
        self.island.set_light_mode(light_mode)
        self._save_session_now()

    def _on_spawn_requested(self, data):
        """Handler do signal bus.spawn_requested — cria o terminal pedido por
        um agente via `POST /spawn`. Roda no UI thread (signal e cross-thread
        com QueuedConnection automatica)."""
        import re
        from pathlib import Path
        from PyQt6.QtCore import QRectF
        from termicanvas.node_factory import DEFAULT_SIZES

        kind = data.get("kind", "")
        name = (data.get("name") or "").strip()
        role_md = data.get("role_md", "")
        parent_cwd = (data.get("parent_cwd") or "").strip() or DEFAULT_CWD
        from_id = data.get("from", "")

        if not name:
            return

        # Slug do nome pra usar como nome de pasta seguro.
        slug = re.sub(r"[^a-z0-9_-]+", "-", name.lower())
        slug = re.sub(r"-+", "-", slug).strip("-_") or "agent"

        # Pasta isolada em <parent>/.termicanvas/<slug>/
        agent_dir = Path(parent_cwd) / ".termicanvas" / slug
        try:
            agent_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            record_error("main.spawn.mkdir", e)
            return

        # Escreve manifesto se for agente Claude/Gemini.
        if kind in ("claude", "gemini") and role_md:
            from termicanvas.agents import (
                AGENT_KINDS,
                TERMICANVAS_MARKER,
                install_termicanvas_permissions,
            )
            manifest_name = AGENT_KINDS[kind]["manifest"]
            manifest_path = agent_dir / manifest_name
            # Remove BOM (﻿) que orquestrador pode ter incluido por
            # acidente — alguns editores prepend BOM em arquivos UTF-8.
            role_md_clean = role_md.lstrip("﻿").strip()
            try:
                content = f"{TERMICANVAS_MARKER}\n\n{role_md_clean}\n"
                manifest_path.write_text(content, encoding="utf-8")
            except Exception as e:
                record_error("main.spawn.manifest", e)
            # Pre-aprova comandos do CLI pra orquestracao fluir sem prompts.
            try:
                install_termicanvas_permissions(str(agent_dir), kind)
            except Exception as e:
                record_error("main.spawn.permissions", e)

        # Calcula posicao abaixo do terminal que pediu o spawn (orquestrador).
        # Se nao encontrar o frame de origem, deixa o canvas posicionar default.
        geometry = None
        src = self.bus._nodes.get(from_id) if from_id else None
        if src and src.frame:
            src_proxy = next(
                (p for p, f in self.canvas.proxies if f is src.frame), None,
            )
            if src_proxy is not None:
                pos = src_proxy.pos()
                w, h = DEFAULT_SIZES.get(kind, (720, 460))
                new_x = pos.x()
                new_y = pos.y() + src.frame.height() + 40  # gap 40px
                geometry = QRectF(new_x, new_y, w, h)

        # Cria o terminal sem dialog, no cwd preparado, com o nome dado.
        try:
            self.factory.create(
                kind, with_dialog=False,
                cwd=str(agent_dir), name=name,
                geometry=geometry,
            )
        except Exception as e:
            record_error("main.spawn.factory", e)

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
        """Habilita botao 'editar role' no header de qualquer terminal de agente
        que tenha cwd. Antes era so 'managed', mas isso escondia o botao em
        toda pasta que ja tinha CLAUDE.md/GEMINI.md (caso super comum)."""
        if not (terminal.agent_kind and terminal.cwd):
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
    # Wrappers finos sobre NodeFactory. A logica de criacao vive em
    # termicanvas/node_factory.py.

    def _add_term(self, shell):
        kind = {"powershell.exe": "powershell", "cmd.exe": "cmd"}.get(shell, "powershell")
        return self.factory.create(kind, with_dialog=True)

    def _add_agent_terminal(self, agent_kind):
        return self.factory.create(agent_kind, with_dialog=True)

    def _add_note(self):
        return self.factory.create("note")

    def _add_agent(self):
        return self.factory.create("agent")

    def _add_prompt(self):
        return self.factory.create("prompt")

    def _add_debug_monitor(self):
        return self.factory.create("debug")

    def _route_output(self, source_frame, text):
        for src, tgt in self.canvas.connections:
            if src is source_frame:
                if isinstance(tgt.inner, AgentWidget):
                    tgt.inner.receive(text)
                elif isinstance(tgt.inner, TerminalWidget):
                    tgt.inner.send(text)
                break

    # ---------- insert mode (drag-to-create) ----------

    def _on_insert_state_changed(self, state):
        active = state in (InsertState.ARMED, InsertState.DRAGGING)
        self.canvas.set_insert_active(active)
        if state != InsertState.DRAGGING:
            self.canvas.clear_drag_preview()

    def _on_insert_commit(self, kind, scene_rect, with_dialog):
        # Snap rect ao grid antes de criar (mesmo grid usado no preview).
        snapped = self.canvas._snap_rect(scene_rect)
        self.factory.create(kind, geometry=snapped, with_dialog=with_dialog)
        self.canvas.clear_drag_preview()

    def _on_island_user_moved(self):
        self._island_manual_position = True

    def _center_island(self):
        self._island_manual_position = False
        self._reposition_island(force=True)

    def _reposition_island(self, force=False):
        if not hasattr(self, "island"):
            return
        if self._island_manual_position and not force:
            return
        margin = 12
        cw = self.canvas.viewport().width()
        iw = self.island.sizeHint().width()
        ih = self.island.sizeHint().height()
        x = max(margin, (cw - iw) // 2)
        y = margin
        self.island.setGeometry(x, y, iw, ih)
        self.island.raise_()

    def _reposition_topbar_overlay(self):
        if not hasattr(self, "topbar"):
            return
        margin = 12
        x = self.canvas.viewport().width() - self.topbar.width() - margin
        y = 8
        self.topbar.move(max(margin, x), y)
        self.topbar.raise_()

    def _reposition_overlays(self):
        self._reposition_island()
        self._reposition_topbar_overlay()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_overlays()

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition_overlays()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if (event.type() == QEvent.Type.MouseButtonPress
                and self.insert.state == InsertState.ARMED):
            target = QApplication.widgetAt(event.globalPosition().toPoint())
            if target is not None:
                w = target
                inside_canvas = False
                while w is not None:
                    if w is self.canvas or w is self.island:
                        inside_canvas = True
                        break
                    w = w.parent()
                if not inside_canvas:
                    self.insert.disarm()
        return super().eventFilter(obj, event)

    # ---------- bus toggle ----------

    def _on_bus_toggled(self, enabled: bool):
        if enabled:
            self._enable_bus()
        else:
            if not self._bus_toggle_warned:
                ok, dont_ask = self._show_bus_off_confirmation()
                if not ok:
                    # user cancelled — keep button green
                    self.topbar.set_bus_state(True)
                    return
                if dont_ask:
                    self._bus_toggle_warned = True
            self._disable_bus()
        self._save_session_now()

    def _enable_bus(self):
        try:
            self.bus.start(self.canvas)
            self._bus_enabled = True
            self.topbar.set_bus_state(True)
        except Exception as e:
            record_error("main.bus_toggle.start", e)
            self._bus_enabled = False
            self.topbar.set_bus_state(False)
            QMessageBox.warning(
                self, "Bus",
                "Falhou ao iniciar o bus. Veja o Debug Monitor.",
            )

    def _disable_bus(self):
        self.canvas.clear_all(bus=self.bus)
        try:
            self.bus.stop()
        except Exception as e:
            record_error("main.bus_toggle.stop", e)
        self._bus_enabled = False
        self.topbar.set_bus_state(False)

    def _show_bus_off_confirmation(self):
        dlg = BusOffConfirmDialog(parent=self)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        return accepted, dlg.dont_ask_again()

    def _save_session_now(self):
        save_session(
            self.canvas,
            self.topbar._accent_color,
            bus_enabled=self._bus_enabled,
            bus_toggle_warned=self._bus_toggle_warned,
            snapshot_load_warned=self._snapshot_load_warned,
            light_mode=self.canvas.is_light_mode(),
        )

    # ---------- snapshots ----------

    def _refresh_snapshots_sidebar(self):
        try:
            items = snapshots_mod.list_snapshots()
        except Exception as e:
            record_error("main.snapshots.list", e)
            items = []
        self.sidebar.set_snapshots(items)

    def _on_snapshot_save_requested(self):
        dlg = SnapshotNameDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name = dlg.chosen_name()
        if not name:
            return
        if snapshots_mod.snapshot_exists(name):
            ans = QMessageBox.question(
                self, "Snapshot",
                f"Ja existe um snapshot '{name}'. Sobrescrever?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
        try:
            snapshots_mod.save_snapshot(
                name, self.canvas, self.topbar._accent_color,
                bus_enabled=self._bus_enabled,
                light_mode=self.canvas.is_light_mode(),
            )
        except Exception as e:
            record_error("main.snapshots.save", e)
            QMessageBox.warning(self, "Snapshot", f"Falhou ao salvar: {e}")
            return
        self._refresh_snapshots_sidebar()

    def _on_snapshot_load_requested(self, file_name: str):
        info = snapshots_mod.load_snapshot(file_name)
        if info is None:
            QMessageBox.warning(self, "Snapshot", "Snapshot nao encontrado ou corrompido.")
            self._refresh_snapshots_sidebar()
            return

        display_name = info.get("name", file_name)
        if not self._snapshot_load_warned:
            dlg = LoadSnapshotConfirmDialog(parent=self, snapshot_name=display_name)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            if dlg.dont_ask_again():
                self._snapshot_load_warned = True
            if dlg.chosen_action() == LoadSnapshotConfirmDialog.SAVE_AND_LOAD:
                self._auto_save_current_snapshot()
        self._apply_snapshot(info)

    def _on_snapshot_rename_requested(self, file_name: str):
        info = snapshots_mod.load_snapshot(file_name)
        if info is None:
            return
        current = info.get("name", file_name)
        dlg = SnapshotNameDialog(
            parent=self, initial_name=current,
            title="Renomear snapshot", confirm_label="Renomear",
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_name = dlg.chosen_name()
        if not new_name or new_name == current:
            return
        if snapshots_mod.rename_snapshot(file_name, new_name) is None:
            QMessageBox.warning(
                self, "Snapshot",
                f"Ja existe outro snapshot com nome similar a '{new_name}'.",
            )
            return
        self._refresh_snapshots_sidebar()

    def _on_snapshot_overwrite_requested(self, file_name: str):
        info = snapshots_mod.load_snapshot(file_name)
        if info is None:
            return
        display_name = info.get("name", file_name)
        ans = QMessageBox.question(
            self, "Snapshot",
            f"Sobrescrever '{display_name}' com o canvas atual?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            snapshots_mod.save_snapshot(
                display_name, self.canvas, self.topbar._accent_color,
                bus_enabled=self._bus_enabled,
                light_mode=self.canvas.is_light_mode(),
            )
        except Exception as e:
            record_error("main.snapshots.overwrite", e)
            QMessageBox.warning(self, "Snapshot", f"Falhou ao sobrescrever: {e}")
            return
        self._refresh_snapshots_sidebar()

    def _on_snapshot_delete_requested(self, file_name: str):
        info = snapshots_mod.load_snapshot(file_name)
        display_name = (info or {}).get("name", file_name)
        ans = QMessageBox.question(
            self, "Snapshot",
            f"Deletar snapshot '{display_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        snapshots_mod.delete_snapshot(file_name)
        self._refresh_snapshots_sidebar()

    def _auto_save_current_snapshot(self):
        """Salva o canvas atual com nome auto-gerado antes de carregar outro snapshot."""
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d-%H%M")
        try:
            snapshots_mod.save_snapshot(
                f"auto {ts}", self.canvas, self.topbar._accent_color,
                bus_enabled=self._bus_enabled,
                light_mode=self.canvas.is_light_mode(),
            )
        except Exception as e:
            record_error("main.snapshots.auto_save", e)

    def _apply_snapshot(self, data: dict):
        """Substitui o canvas atual pelo conteudo de um snapshot. Restaura
        bus state e tema (dark/light) exatamente como estavam quando salvo."""
        cs = data.get("canvas", {})
        # Fallback p/ snapshots antigos sem bus_enabled: liga se houver nodes.
        target_bus = cs.get("bus_enabled", bool(data.get("nodes")))

        # 1. Limpa canvas atual
        self.canvas.clear_all(bus=self.bus)

        # 2. Ajusta bus state para casar com o snapshot
        if target_bus and not self._bus_enabled:
            self._enable_bus()
        elif not target_bus and self._bus_enabled:
            self._disable_bus()

        # 3. Aplica o conteudo do snapshot (nodes + viewport + tema)
        self._load_session_nodes(data)
        self._apply_session_viewport(data)

        # 4. Persiste o estado novo
        self._save_session_now()
        self._refresh_snapshots_sidebar()

    def closeEvent(self, e):
        self._save_session_now()
        if self._bus_enabled:
            for proxy, frame in self.canvas.proxies:
                if isinstance(frame.inner, TerminalWidget):
                    frame.inner.shutdown()
            try:
                self.bus.stop()
            except Exception:
                pass
        super().closeEvent(e)


def main():
    from termicanvas.diagnostics import install_excepthooks
    install_excepthooks()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

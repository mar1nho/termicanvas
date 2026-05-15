import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def main_window(qt_app, monkeypatch, tmp_path):
    from termicanvas import session as session_mod, config as config_mod
    monkeypatch.setattr(session_mod, "SESSION_FILE", tmp_path / "session.json")
    config_mod.set_default_cwd(str(tmp_path))
    from main import MainWindow
    w = MainWindow()
    yield w
    w.close()


def test_factory_creates_note_with_default_geometry(main_window):
    from termicanvas.node_factory import NodeFactory
    factory = NodeFactory(main_window)
    frame = factory.create("note")
    assert frame is not None
    assert frame in [f for _, f in main_window.canvas.proxies]


def test_factory_creates_note_with_custom_geometry(main_window):
    from termicanvas.node_factory import NodeFactory
    factory = NodeFactory(main_window)
    frame = factory.create("note", geometry=QRectF(100, 200, 480, 320))
    proxy = next(p for p, f in main_window.canvas.proxies if f is frame)
    assert proxy.pos().x() == 100 and proxy.pos().y() == 200
    assert frame.width() == 480 and frame.height() == 320


def test_factory_debug_is_singleton(main_window):
    from termicanvas.node_factory import NodeFactory
    factory = NodeFactory(main_window)
    f1 = factory.create("debug")
    f2 = factory.create("debug")
    assert f1 is f2  # second call returns existing


def test_factory_creates_preview_node(main_window):
    from termicanvas.node_factory import NodeFactory
    from termicanvas.preview import PreviewWidget

    factory = NodeFactory(main_window)
    frame = factory.create("preview")
    assert frame is not None
    assert isinstance(frame.inner, PreviewWidget)
    assert frame.header.compact_btn.isVisible()


def test_preview_node_compacts_and_expands(main_window):
    from termicanvas.node_factory import NodeFactory

    frame = NodeFactory(main_window).create("preview")
    frame.set_compacted(True)
    assert frame.width() == 80
    assert frame.height() == 80
    assert frame.body.isHidden()

    frame.set_compacted(False)
    assert frame.width() >= 260
    assert frame.height() >= 180
    assert frame.body.isVisible()


def test_compacted_preview_header_still_drags(main_window):
    from PyQt6.QtCore import QPointF
    from termicanvas.node_factory import NodeFactory

    frame = NodeFactory(main_window).create("preview")
    frame.set_compacted(True)
    moved = []
    frame.header.drag_moved.connect(lambda delta: moved.append(delta))
    frame.header.drag_moved.emit(QPointF(5, 5))
    assert moved


def test_factory_unknown_kind_returns_none(main_window):
    from termicanvas.node_factory import NodeFactory
    factory = NodeFactory(main_window)
    assert factory.create("invalid_kind") is None


def test_agent_dialog_exposes_shell_choice(qt_app):
    from termicanvas.dialogs import TerminalLaunchDialog

    dlg = TerminalLaunchDialog("Claude Code", default_name="Claude 1", agent_kind="claude")
    assert dlg.chosen_shell() == "powershell.exe"
    dlg.shell_combo.setCurrentIndex(1)
    assert dlg.chosen_shell() == "cmd.exe"


def test_unified_launch_dialog_uses_choice_buttons(qt_app, tmp_path, monkeypatch):
    from termicanvas import config as config_mod
    from termicanvas.dialogs import UnifiedLaunchDialog

    config_mod.set_default_cwd(str(tmp_path))
    dlg = UnifiedLaunchDialog()
    assert dlg.chosen_kind() == "powershell"
    assert hasattr(dlg, "kind_buttons")
    assert "claude" in dlg.kind_buttons

    dlg.kind_buttons["claude"].click()
    assert dlg.chosen_kind() == "claude"
    assert not dlg.shell_combo.isHidden()

    dlg.kind_buttons["cmd"].click()
    assert dlg.chosen_kind() == "cmd"
    assert "QCheckBox::indicator" in dlg._check_style()
    assert "border:" in dlg._check_style()


def test_canvas_reorders_frames(main_window):
    from termicanvas.node_factory import NodeFactory

    factory = NodeFactory(main_window)
    first = factory.create("note")
    second = factory.create("preview")

    frames = [f for _p, f in main_window.canvas.proxies]
    assert frames.index(first) < frames.index(second)

    main_window.canvas.move_frame_in_order(second, -1)
    frames = [f for _p, f in main_window.canvas.proxies]
    assert frames.index(second) < frames.index(first)


def test_sidebar_categorizes_widgets(main_window):
    from termicanvas.node_factory import NodeFactory

    frame = NodeFactory(main_window).create("preview")
    assert main_window.sidebar._category_for_frame(frame) == "widget"


def test_sidebar_places_created_nodes_before_correct_empty_label(main_window):
    from termicanvas.node_factory import NodeFactory

    sidebar = main_window.sidebar
    agent = NodeFactory(main_window).create("claude")
    terminal = NodeFactory(main_window).create("powershell")
    widget = NodeFactory(main_window).create("preview")

    agent_chip = sidebar.chips[agent]
    terminal_chip = sidebar.chips[terminal]
    widget_chip = sidebar.chips[widget]

    assert sidebar._col.indexOf(agent_chip) < sidebar._col.indexOf(sidebar._agent_empty)
    assert sidebar._col.indexOf(terminal_chip) < sidebar._col.indexOf(sidebar._empty)
    assert sidebar._col.indexOf(widget_chip) < sidebar._col.indexOf(sidebar._widget_empty)
    assert sidebar._col.indexOf(sidebar._agent_header) < sidebar._col.indexOf(agent_chip) < sidebar._col.indexOf(sidebar._agent_empty)
    assert sidebar._col.indexOf(sidebar._term_header) < sidebar._col.indexOf(terminal_chip) < sidebar._col.indexOf(sidebar._empty)
    assert sidebar._col.indexOf(sidebar._widget_header) < sidebar._col.indexOf(widget_chip) < sidebar._col.indexOf(sidebar._widget_empty)

    sidebar._agent_header.set_expanded(False)
    sidebar._on_agents_toggled(False)
    assert agent_chip.isHidden()
    assert not terminal_chip.isHidden()
    assert not widget_chip.isHidden()


def test_sidebar_reclassifies_existing_nodes_on_resync(main_window):
    from termicanvas.node_factory import NodeFactory

    sidebar = main_window.sidebar
    factory = NodeFactory(main_window)
    widget = factory.create("preview")
    agent = factory.create("codex")
    terminal = factory.create("cmd")

    sidebar.sync(main_window.canvas)

    assert sidebar._category_for_frame(agent) == "agent"
    assert sidebar._category_for_frame(terminal) == "terminal"
    assert sidebar._category_for_frame(widget) == "widget"
    assert sidebar._col.indexOf(sidebar.chips[agent]) < sidebar._col.indexOf(sidebar._agent_empty)
    assert sidebar._col.indexOf(sidebar.chips[terminal]) < sidebar._col.indexOf(sidebar._empty)
    assert sidebar._col.indexOf(sidebar.chips[widget]) < sidebar._col.indexOf(sidebar._widget_empty)


def test_codex_uses_agents_manifest(tmp_path):
    from termicanvas.agents import ORCHESTRATOR_BEGIN, managed_manifest_path, promote_to_orchestrator

    manifest = managed_manifest_path(tmp_path, "codex")
    assert manifest.name == "AGENTS.md"

    promoted = promote_to_orchestrator(tmp_path, "codex")
    assert promoted == manifest
    assert promoted.exists()
    content = promoted.read_text(encoding="utf-8")
    assert ORCHESTRATOR_BEGIN in content


def test_agent_startup_loads_fnm_for_powershell():
    from types import SimpleNamespace
    from termicanvas.terminal import TerminalWidget

    terminal = SimpleNamespace(agent_kind="claude", _startup_command="claude")
    command = TerminalWidget._startup_command_for_shell(terminal, "powershell.exe")

    assert "fnm env --use-on-cd --shell powershell" in command
    assert command.endswith("; claude")


def test_agent_startup_loads_fnm_for_cmd():
    from types import SimpleNamespace
    from termicanvas.terminal import TerminalWidget

    terminal = SimpleNamespace(agent_kind="claude", _startup_command="claude")
    command = TerminalWidget._startup_command_for_shell(terminal, "cmd.exe")

    assert "fnm env --use-on-cd --shell cmd" in command
    assert command.endswith("& claude")

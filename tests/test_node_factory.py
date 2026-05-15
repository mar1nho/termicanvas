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


def test_codex_uses_agents_manifest(tmp_path):
    from termicanvas.agents import ORCHESTRATOR_BEGIN, managed_manifest_path, promote_to_orchestrator

    manifest = managed_manifest_path(tmp_path, "codex")
    assert manifest.name == "AGENTS.md"

    promoted = promote_to_orchestrator(tmp_path, "codex")
    assert promoted == manifest
    assert promoted.exists()
    content = promoted.read_text(encoding="utf-8")
    assert ORCHESTRATOR_BEGIN in content

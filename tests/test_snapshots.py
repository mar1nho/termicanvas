"""Tests for the snapshots module — name sanitization, save/load round-trip,
list/rename/delete."""

import json
import time
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def snap_dir(tmp_path, monkeypatch):
    """Patch SNAPSHOTS_DIR em config + snapshots para tmp_path."""
    from termicanvas import config as config_mod
    from termicanvas import snapshots as snap_mod
    fake_dir = tmp_path / "snapshots"
    fake_dir.mkdir()
    monkeypatch.setattr(config_mod, "SNAPSHOTS_DIR", fake_dir)
    monkeypatch.setattr(snap_mod, "SNAPSHOTS_DIR", fake_dir)
    return fake_dir


@pytest.fixture
def fake_canvas(qt_app):
    """Canvas-like com proxies vazios e transform identidade."""
    canvas = MagicMock()
    canvas.proxies = []
    canvas.connections = []

    class T:
        def m11(self): return 1.0
    canvas.transform = lambda: T()

    class S:
        def value(self): return 0
    canvas.horizontalScrollBar = lambda: S()
    canvas.verticalScrollBar = lambda: S()
    return canvas


# ---------- name sanitization ----------

def test_sanitize_basic():
    from termicanvas.snapshots import _sanitize_file_name
    assert _sanitize_file_name("My Workflow") == "my-workflow"


def test_sanitize_strips_special_chars():
    from termicanvas.snapshots import _sanitize_file_name
    assert _sanitize_file_name("Test #1!") == "test-1"


def test_sanitize_collapses_whitespace_and_dashes():
    from termicanvas.snapshots import _sanitize_file_name
    assert _sanitize_file_name("   foo   bar   ") == "foo-bar"
    assert _sanitize_file_name("--a--b--") == "a-b"


def test_sanitize_blocks_path_traversal():
    from termicanvas.snapshots import _sanitize_file_name
    assert _sanitize_file_name("../../etc/passwd") == "etc-passwd"
    assert _sanitize_file_name("foo/bar") == "foo-bar"


def test_sanitize_empty_or_invalid_yields_unnamed():
    from termicanvas.snapshots import _sanitize_file_name
    assert _sanitize_file_name("") == "unnamed"
    assert _sanitize_file_name("---") == "unnamed"
    assert _sanitize_file_name("!@#$") == "unnamed"


def test_sanitize_preserves_underscores():
    from termicanvas.snapshots import _sanitize_file_name
    assert _sanitize_file_name("a__b") == "a__b"


# ---------- save/load round-trip ----------

def test_save_and_load_round_trip(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    file_name = snap_mod.save_snapshot("My Save", fake_canvas, "#5a8dff")
    assert file_name == "my-save"
    assert (snap_dir / "my-save.json").exists()

    data = snap_mod.load_snapshot(file_name)
    assert data is not None
    assert data["name"] == "My Save"
    assert data["file_name"] == "my-save"
    assert data["version"] == 1
    assert data["canvas"]["accent_color"] == "#5a8dff"
    assert data["nodes"] == []
    assert data["connections"] == []
    assert "created_at" in data
    assert "modified_at" in data


def test_save_overwrites_preserves_created_at(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    snap_mod.save_snapshot("X", fake_canvas)
    first = snap_mod.load_snapshot("x")
    first_created = first["created_at"]

    time.sleep(0.01)
    snap_mod.save_snapshot("X", fake_canvas)
    second = snap_mod.load_snapshot("x")

    assert second["created_at"] == first_created
    assert second["modified_at"] >= first["modified_at"]


def test_load_returns_none_for_missing(snap_dir):
    from termicanvas import snapshots as snap_mod
    assert snap_mod.load_snapshot("does-not-exist") is None


def test_load_returns_none_for_corrupt_json(snap_dir):
    from termicanvas import snapshots as snap_mod
    (snap_dir / "broken.json").write_text("{not json", encoding="utf-8")
    assert snap_mod.load_snapshot("broken") is None


# ---------- list ----------

def test_list_empty(snap_dir):
    from termicanvas import snapshots as snap_mod
    assert snap_mod.list_snapshots() == []


def test_list_sorted_by_modified_desc(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    snap_mod.save_snapshot("Old", fake_canvas)
    time.sleep(0.01)
    snap_mod.save_snapshot("New", fake_canvas)

    items = snap_mod.list_snapshots()
    assert len(items) == 2
    assert items[0]["name"] == "New"
    assert items[1]["name"] == "Old"


def test_list_node_count_reflects_nodes(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    # Forge a snapshot file with 3 nodes manually
    payload = {
        "version": 1, "name": "Test", "file_name": "test",
        "created_at": 0, "modified_at": 100,
        "canvas": {"scale": 1.0, "scroll_h": 0, "scroll_v": 0, "accent_color": "#000"},
        "nodes": [{"type": "note"}, {"type": "note"}, {"type": "note"}],
        "connections": [],
    }
    (snap_dir / "test.json").write_text(json.dumps(payload), encoding="utf-8")
    items = snap_mod.list_snapshots()
    assert items[0]["node_count"] == 3


def test_list_skips_corrupt_json(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    snap_mod.save_snapshot("Good", fake_canvas)
    (snap_dir / "broken.json").write_text("{nope", encoding="utf-8")
    items = snap_mod.list_snapshots()
    assert len(items) == 1
    assert items[0]["name"] == "Good"


# ---------- delete ----------

def test_delete_removes_file(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    snap_mod.save_snapshot("X", fake_canvas)
    assert snap_mod.delete_snapshot("x") is True
    assert not (snap_dir / "x.json").exists()


def test_delete_returns_false_for_missing(snap_dir):
    from termicanvas import snapshots as snap_mod
    assert snap_mod.delete_snapshot("never-existed") is False


# ---------- rename ----------

def test_rename_changes_display_name_same_file(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    snap_mod.save_snapshot("Test", fake_canvas)
    new_name = snap_mod.rename_snapshot("test", "Test")  # mesmo file_name
    assert new_name == "test"
    data = snap_mod.load_snapshot("test")
    assert data["name"] == "Test"


def test_rename_creates_new_file_deletes_old(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    snap_mod.save_snapshot("Old Name", fake_canvas)
    new_name = snap_mod.rename_snapshot("old-name", "Brand New")
    assert new_name == "brand-new"
    assert (snap_dir / "brand-new.json").exists()
    assert not (snap_dir / "old-name.json").exists()
    data = snap_mod.load_snapshot("brand-new")
    assert data["name"] == "Brand New"
    assert data["file_name"] == "brand-new"


def test_rename_returns_none_on_collision(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    snap_mod.save_snapshot("First", fake_canvas)
    snap_mod.save_snapshot("Second", fake_canvas)
    # tentar renomear "first" -> "Second" (sanitized = "second", ja existe)
    assert snap_mod.rename_snapshot("first", "Second") is None
    # ambos devem continuar existindo
    assert snap_mod.load_snapshot("first") is not None
    assert snap_mod.load_snapshot("second") is not None


def test_rename_returns_none_for_missing(snap_dir):
    from termicanvas import snapshots as snap_mod
    assert snap_mod.rename_snapshot("does-not-exist", "Whatever") is None


# ---------- snapshot_exists ----------

def test_snapshot_exists(snap_dir, fake_canvas):
    from termicanvas import snapshots as snap_mod
    assert snap_mod.snapshot_exists("My Test") is False
    snap_mod.save_snapshot("My Test", fake_canvas)
    assert snap_mod.snapshot_exists("My Test") is True
    # mesmo nome com casing/punctuacao diferente sanitiza pra mesma chave
    assert snap_mod.snapshot_exists("MY TEST!") is True


# ---------- session.json round-trip do flag ----------

def test_session_persists_snapshot_load_warned(qt_app, tmp_path, monkeypatch):
    from termicanvas import session as session_mod
    fake_path = tmp_path / "session.json"
    monkeypatch.setattr(session_mod, "SESSION_FILE", fake_path)

    canvas = MagicMock()
    canvas.proxies = []
    canvas.connections = []
    class T:
        def m11(self): return 1.0
    canvas.transform = lambda: T()
    class S:
        def value(self): return 0
    canvas.horizontalScrollBar = lambda: S()
    canvas.verticalScrollBar = lambda: S()

    session_mod.save_session(canvas, "#5a8dff", snapshot_load_warned=True)
    data = json.loads(fake_path.read_text(encoding="utf-8"))
    assert data["canvas"]["snapshot_load_warned"] is True

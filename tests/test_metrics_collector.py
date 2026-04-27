"""Tests for MetricsCollector — snapshot building, weakref behavior, lifecycle."""

import gc
import weakref
from unittest.mock import MagicMock

import pytest

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_collector_stops_timer_on_stop(qt_app):
    from termicanvas.monitor import MetricsCollector
    canvas = MagicMock()
    canvas.proxies = []
    bus = MagicMock()
    bus._queue = []
    bus.findChildren = MagicMock(return_value=[])

    collector = MetricsCollector(canvas, bus)
    assert collector._timer.isActive() is True

    collector.stop()
    assert collector._timer.isActive() is False


def test_snapshot_has_expected_fields(qt_app):
    from termicanvas.monitor import MetricsCollector, MetricsSnapshot
    canvas = MagicMock()
    canvas.proxies = []
    bus = MagicMock()
    bus._queue = ["msg1", "msg2"]
    bus.findChildren = MagicMock(return_value=[])

    collector = MetricsCollector(canvas, bus)
    try:
        snap = collector._build_snapshot()
        assert isinstance(snap, MetricsSnapshot)
        assert snap.queue_size == 2
        assert snap.n_terminals == 0
        assert snap.n_nodes == 0
        assert snap.timestamp > 0
        assert isinstance(snap.terminals, tuple)
    finally:
        collector.stop()


def test_canvas_weakref_does_not_keep_canvas_alive(qt_app):
    from termicanvas.monitor import MetricsCollector

    class DummyCanvas:
        proxies = []

    canvas = DummyCanvas()
    bus = MagicMock()
    bus._queue = []
    bus.findChildren = MagicMock(return_value=[])

    collector = MetricsCollector(canvas, bus)
    canvas_ref = weakref.ref(canvas)

    del canvas
    gc.collect()

    assert canvas_ref() is None, (
        "DummyCanvas should be GC'd; collector should not hold a strong ref"
    )

    # Building a snapshot now should not crash — canvas weakref returns None
    snap = collector._build_snapshot()
    assert snap.n_nodes == 0
    collector.stop()


def test_chars_per_sec_delta(qt_app):
    """Verifies chars/sec is computed as delta between consecutive ticks."""
    from termicanvas.monitor import MetricsCollector
    canvas = MagicMock()
    bus = MagicMock()
    bus._queue = []
    bus.findChildren = MagicMock(return_value=[])

    # Build a fake terminal that looks like TerminalWidget for isinstance via spec
    from termicanvas.terminal import TerminalWidget
    fake_term = MagicMock(spec=TerminalWidget)
    fake_term.node_id = "t1"
    fake_term.alive = True
    fake_term._raw_buf = "a" * 1000
    fake_term.activity = "idle"
    fake_term.objectName = MagicMock(return_value="Term 1")

    fake_frame = MagicMock()
    fake_frame.inner = fake_term

    canvas.proxies = [(MagicMock(), fake_frame)]

    collector = MetricsCollector(canvas, bus)
    try:
        snap1 = collector._build_snapshot()
        # First tick: chars/sec equals current length minus initial estimate (current length)
        # → 0
        assert snap1.terminals[0].chars_per_sec == 0

        # Second tick: bump raw_buf by 1500 chars
        fake_term._raw_buf = "a" * 2500
        snap2 = collector._build_snapshot()
        assert snap2.terminals[0].chars_per_sec == 1500
    finally:
        collector.stop()


def test_percentile_helper(qt_app):
    from termicanvas.monitor import _percentile
    samples = sorted([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    # p50 should be ~5.5 with linear interpolation
    assert abs(_percentile(samples, 50.0) - 5.5) < 0.01
    # p100 = 10
    assert _percentile(samples, 100.0) == 10.0
    # p0 = 1
    assert _percentile(samples, 0.0) == 1.0
    # Empty
    assert _percentile([], 50.0) == 0.0
    # Single value
    assert _percentile([42.0], 95.0) == 42.0

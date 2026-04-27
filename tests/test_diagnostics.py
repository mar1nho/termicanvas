"""Tests for termicanvas.diagnostics: error buffer, render times, excepthook chain."""

import sys
import threading
import pytest


def test_record_error_adds_to_buffer():
    from termicanvas import diagnostics
    diagnostics._errors.clear()

    try:
        raise ValueError("boom")
    except ValueError as e:
        diagnostics.record_error("test_source", e)

    errors = diagnostics.iter_errors()
    assert len(errors) == 1
    rec = errors[0]
    assert rec.source == "test_source"
    assert rec.exc_type == "ValueError"
    assert "boom" in rec.message
    assert "test_record_error_adds_to_buffer" in rec.stack


def test_errors_buffer_respects_maxlen():
    from termicanvas import diagnostics
    diagnostics._errors.clear()

    for i in range(250):
        try:
            raise RuntimeError(f"err {i}")
        except RuntimeError as e:
            diagnostics.record_error("loop", e)

    errors = diagnostics.iter_errors()
    assert len(errors) == 200
    # Oldest dropped: first remaining error message contains "err 50"
    assert "err 50" in errors[0].message
    assert "err 249" in errors[-1].message


def test_render_times_buffer():
    from termicanvas import diagnostics
    diagnostics._render_times.clear()

    diagnostics.record_render_time(4.2)
    diagnostics.record_render_time(8.1)
    diagnostics.record_render_time(15.7)

    times = diagnostics.iter_render_times()
    assert times == [4.2, 8.1, 15.7]


def test_render_times_buffer_maxlen():
    from termicanvas import diagnostics
    diagnostics._render_times.clear()

    for i in range(700):
        diagnostics.record_render_time(float(i))

    times = diagnostics.iter_render_times()
    assert len(times) == 600
    assert times[0] == 100.0   # first 100 dropped
    assert times[-1] == 699.0


def test_install_excepthooks_chains_previous_sys_hook():
    from termicanvas import diagnostics
    diagnostics._errors.clear()

    # Save original to restore at end
    original = sys.excepthook

    chained_calls = []
    def marker(*args):
        chained_calls.append(args)
    sys.excepthook = marker

    try:
        diagnostics.install_excepthooks()
        assert getattr(sys.excepthook, "_termicanvas_installed", False) is True

        # Simulate uncaught exception path
        try:
            raise KeyError("uncaught")
        except KeyError:
            sys.excepthook(*sys.exc_info())

        errors = diagnostics.iter_errors()
        assert any(e.source == "excepthook" for e in errors)
        assert len(chained_calls) == 1, "previous hook should be chained"
    finally:
        sys.excepthook = original


def test_install_excepthooks_idempotent():
    from termicanvas import diagnostics
    original = sys.excepthook
    try:
        diagnostics.install_excepthooks()
        first = sys.excepthook
        diagnostics.install_excepthooks()
        # Same hook, not double-wrapped
        assert sys.excepthook is first
    finally:
        sys.excepthook = original

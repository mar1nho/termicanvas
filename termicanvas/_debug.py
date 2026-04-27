"""Temporary instrumentation for memory leak diagnosis. Removed in Task 7."""

import os
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

try:
    import psutil
    _proc = psutil.Process(os.getpid())
except ImportError:
    _proc = None


def snapshot(label, bus):
    rss_mb = (_proc.memory_info().rss / 1024 / 1024) if _proc else -1
    n_nodes = len(bus._nodes) if bus else -1
    n_timers = _count_timers(bus)
    print(f"[debug:{label}] nodes={n_nodes} timers={n_timers} rss={rss_mb:.1f}MB")


def _count_timers(bus):
    """Counts unique QTimer instances reachable from the app's widgets and the bus.

    QApplication.findChildren misses widget-parented timers because top-level
    widgets are not children of the QApplication. We walk all widgets via
    allWidgets() and add bus-parented timers (Bus._tick).
    """
    app = QApplication.instance()
    if not app:
        return -1
    seen = set()
    for w in app.allWidgets():
        for t in w.findChildren(QTimer):
            seen.add(id(t))
    if bus is not None:
        for t in bus.findChildren(QTimer):
            seen.add(id(t))
    return len(seen)

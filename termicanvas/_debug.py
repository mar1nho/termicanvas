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
    app = QApplication.instance()
    n_timers = len(app.findChildren(QTimer)) if app else -1
    n_nodes = len(bus._nodes) if bus else -1
    print(f"[debug:{label}] nodes={n_nodes} timers={n_timers} rss={rss_mb:.1f}MB")

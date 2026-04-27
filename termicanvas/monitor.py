"""Debug Monitor: collector + UI widget for live metrics.

Two-layer design:
- MetricsCollector (QObject): polls 1Hz, exposes snapshot via signal.
- DebugMonitorWidget (QWidget): subscribes to collector and renders 4 tabs.

Both must clean up on close: see shutdown() chain.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from .tokens import (
    ACCENT,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


# ---------- data model ----------

@dataclass(frozen=True)
class TerminalMetric:
    node_id: str
    name: str
    raw_buf_kb: int
    chars_per_sec: int
    activity: str
    alive: bool


@dataclass(frozen=True)
class MetricsSnapshot:
    timestamp: float
    rss_mb: float
    cpu_pct: float
    n_terminals: int
    n_nodes: int
    n_timers: int
    queue_size: int
    render_p50_ms: float
    render_p95_ms: float
    render_p99_ms: float
    terminals: tuple = field(default_factory=tuple)


# ---------- visual primitives ----------

class Sparkline(QWidget):
    """Tiny line chart of a numeric deque. Adapts to widget width.

    Empty/single-point case renders a centered em-dash.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(32)
        self.setMaximumHeight(50)
        self._data: list[float] = []
        self._color = QColor(ACCENT)

    def set_data(self, points):
        self._data = list(points)
        self.update()

    def set_color(self, hex_color: str):
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.fillRect(rect, QColor(BG_ELEVATED))

        if len(self._data) < 2:
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—")
            p.end()
            return

        lo = min(self._data)
        hi = max(self._data)
        span = hi - lo if hi > lo else 1.0
        n = len(self._data)
        left, top = float(rect.left()) + 2, float(rect.top()) + 2
        right, bottom = float(rect.right()) - 2, float(rect.bottom()) - 2
        w = max(1.0, right - left)
        h = max(1.0, bottom - top)

        def _xy(i, v):
            x = left + (i / (n - 1)) * w
            y = bottom - ((v - lo) / span) * h
            return QPointF(x, y)

        # Filled area under the line
        path_pts = [_xy(i, v) for i, v in enumerate(self._data)]
        fill_color = QColor(self._color)
        fill_color.setAlpha(60)
        p.setBrush(QBrush(fill_color))
        p.setPen(Qt.PenStyle.NoPen)
        polygon = [QPointF(left, bottom)] + path_pts + [QPointF(right, bottom)]
        p.drawPolygon(*polygon)

        # Line
        pen = QPen(self._color)
        pen.setWidthF(1.5)
        p.setPen(pen)
        for i in range(1, len(path_pts)):
            p.drawLine(path_pts[i - 1], path_pts[i])
        p.end()


class Histogram(QWidget):
    """Bucket-based histogram of render times in ms.

    Buckets: 0-1, 1-2, 2-5, 5-10, 10-20, 20-50, 50+.
    """

    BUCKETS = [(0, 1), (1, 2), (2, 5), (5, 10), (10, 20), (20, 50), (50, float("inf"))]
    LABELS = ["0-1", "1-2", "2-5", "5-10", "10-20", "20-50", "50+"]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self._counts = [0] * len(self.BUCKETS)

    def set_samples(self, samples_ms):
        counts = [0] * len(self.BUCKETS)
        for s in samples_ms:
            for i, (lo, hi) in enumerate(self.BUCKETS):
                if lo <= s < hi:
                    counts[i] += 1
                    break
        self._counts = counts
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.fillRect(rect, QColor(BG_ELEVATED))

        max_count = max(self._counts) if self._counts else 0
        if max_count == 0:
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "no samples")
            p.end()
            return

        n = len(self.BUCKETS)
        margin = 4
        label_h = 14
        bar_area_h = max(1, rect.height() - label_h - margin * 2)
        bar_w = max(1.0, (rect.width() - margin * 2) / n)

        for i, (count, label) in enumerate(zip(self._counts, self.LABELS)):
            x = rect.left() + margin + i * bar_w
            bar_h = (count / max_count) * bar_area_h if max_count else 0
            top = rect.top() + margin + (bar_area_h - bar_h)
            bar_rect = QRectF(x + 2, top, bar_w - 4, bar_h)
            color = QColor(ACCENT)
            p.fillRect(bar_rect, color)

            # Label
            label_rect = QRectF(x, rect.bottom() - label_h, bar_w, label_h)
            p.setPen(QColor(TEXT_MUTED))
            font = p.font()
            font.setPointSize(7)
            p.setFont(font)
            p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
        p.end()


# ---------- collector ----------

import os
import time
import weakref

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

try:
    import psutil
    _proc = psutil.Process(os.getpid())
except ImportError:
    _proc = None

from . import diagnostics
from .terminal import TerminalWidget


def _percentile(sorted_values, pct):
    """Linear-interpolation percentile. sorted_values must be pre-sorted."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return float(sorted_values[f])
    return float(sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f))


class MetricsCollector(QObject):
    """Polls metrics at 1Hz and emits MetricsSnapshot.

    Holds weakref to canvas + bus to avoid keeping them alive. Observed
    terminals live in a WeakSet, so closed terminals fall out automatically.
    Sustained-alert state (chars/sec > 5000 for 3 ticks) is tracked here, not
    in the UI.

    Lifecycle: caller must invoke stop() before discarding the collector
    (typically from DebugMonitorWidget.shutdown).
    """

    snapshot_ready = pyqtSignal(object)  # emits MetricsSnapshot

    HISTORY_LEN = 300  # 5 min at 1Hz
    SUSTAINED_ALERT_THRESHOLD = 5000  # chars/sec

    def __init__(self, canvas, bus, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._canvas_ref = weakref.ref(canvas)
        self._bus_ref = weakref.ref(bus)
        self._observed_terminals: "weakref.WeakSet[TerminalWidget]" = weakref.WeakSet()
        self._refresh_observed_terminals()

        # Sparkline histories
        self.rss_history: deque = deque(maxlen=self.HISTORY_LEN)
        self.cpu_history: deque = deque(maxlen=self.HISTORY_LEN)
        self.n_terminals_history: deque = deque(maxlen=self.HISTORY_LEN)
        self.queue_history: deque = deque(maxlen=self.HISTORY_LEN)
        self.render_p95_history: deque = deque(maxlen=self.HISTORY_LEN)

        # Per-terminal state for chars/sec delta
        self._last_raw_buf_len: dict[str, int] = {}
        self._sustained_alert_count: dict[str, int] = {}

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _refresh_observed_terminals(self):
        """Rescans canvas.proxies for live TerminalWidgets and re-populates the WeakSet."""
        canvas = self._canvas_ref()
        if canvas is None:
            return
        new_set: "weakref.WeakSet[TerminalWidget]" = weakref.WeakSet()
        for _, frame in getattr(canvas, "proxies", []):
            inner = getattr(frame, "inner", None)
            if isinstance(inner, TerminalWidget):
                new_set.add(inner)
        self._observed_terminals = new_set

    def stop(self):
        """Cleanup path. Stop the timer, drop refs, schedule deletion."""
        self._timer.stop()
        self._observed_terminals = weakref.WeakSet()
        self.deleteLater()

    def _tick(self):
        """Build a MetricsSnapshot and emit it. Called every 1000ms."""
        try:
            snapshot = self._build_snapshot()
        except Exception as e:
            diagnostics.record_error("monitor.MetricsCollector._tick", e)
            return

        # Update histories
        self.rss_history.append(snapshot.rss_mb)
        self.cpu_history.append(snapshot.cpu_pct)
        self.n_terminals_history.append(snapshot.n_terminals)
        self.queue_history.append(snapshot.queue_size)
        self.render_p95_history.append(snapshot.render_p95_ms)

        self.snapshot_ready.emit(snapshot)

    def _build_snapshot(self):
        canvas = self._canvas_ref()
        bus = self._bus_ref()

        rss_mb = (_proc.memory_info().rss / 1024 / 1024) if _proc else -1.0
        cpu_pct = _proc.cpu_percent(interval=None) if _proc else -1.0

        n_nodes = len(getattr(canvas, "proxies", [])) if canvas else 0

        # Refresh observed terminals lazily — in case the canvas opened/closed since last tick
        self._refresh_observed_terminals()
        live_terminals = [t for t in self._observed_terminals if self._safe_alive(t)]
        n_terminals = len(live_terminals)

        # Count timers reachable from the app + bus
        n_timers = 0
        app = QApplication.instance()
        if app is not None:
            seen = set()
            for w in app.allWidgets():
                for t in w.findChildren(QTimer):
                    seen.add(id(t))
            if bus is not None:
                for t in bus.findChildren(QTimer):
                    seen.add(id(t))
            n_timers = len(seen)

        queue_size = len(getattr(bus, "_queue", [])) if bus else 0

        # Render time percentiles from diagnostics buffer
        samples = sorted(diagnostics.iter_render_times())
        p50 = _percentile(samples, 50.0)
        p95 = _percentile(samples, 95.0)
        p99 = _percentile(samples, 99.0)

        # Per-terminal metrics
        terminals: list[TerminalMetric] = []
        for t in live_terminals:
            term_metric = self._terminal_metric(t)
            if term_metric is not None:
                terminals.append(term_metric)

        return MetricsSnapshot(
            timestamp=time.time(),
            rss_mb=rss_mb,
            cpu_pct=cpu_pct,
            n_terminals=n_terminals,
            n_nodes=n_nodes,
            n_timers=n_timers,
            queue_size=queue_size,
            render_p50_ms=p50,
            render_p95_ms=p95,
            render_p99_ms=p99,
            terminals=tuple(terminals),
        )

    def _safe_alive(self, terminal):
        """True if Python+C++ side both alive. Catches RuntimeError from a
        deleted Qt object whose Python wrapper hasn't been GC'd yet."""
        try:
            return bool(getattr(terminal, "alive", False))
        except RuntimeError:
            return False

    def _terminal_metric(self, t):
        try:
            node_id = getattr(t, "node_id", None) or f"id{id(t):x}"
            name = getattr(t, "objectName", lambda: "")() or "Terminal"
            raw_buf = getattr(t, "_raw_buf", "") or ""
            raw_buf_kb = len(raw_buf) // 1024
            activity = getattr(t, "activity", "") or ""
            alive = bool(getattr(t, "alive", False))
        except RuntimeError:
            return None

        # chars/sec — delta from last known length
        prev = self._last_raw_buf_len.get(node_id, len(raw_buf))
        chars_per_sec = max(0, len(raw_buf) - prev)
        self._last_raw_buf_len[node_id] = len(raw_buf)

        # Sustained alert tracking
        if chars_per_sec > self.SUSTAINED_ALERT_THRESHOLD:
            self._sustained_alert_count[node_id] = self._sustained_alert_count.get(node_id, 0) + 1
        else:
            self._sustained_alert_count[node_id] = 0

        return TerminalMetric(
            node_id=node_id,
            name=name,
            raw_buf_kb=raw_buf_kb,
            chars_per_sec=chars_per_sec,
            activity=activity[:30],
            alive=alive,
        )

    def is_sustained_alert(self, node_id: str) -> bool:
        return self._sustained_alert_count.get(node_id, 0) >= 3

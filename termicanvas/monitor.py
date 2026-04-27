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

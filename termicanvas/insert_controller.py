"""InsertController — state machine pura pro modo de inserção de nodes.

Sem GUI. ToolIsland chama .arm()/.disarm(); CanvasView chama
.start_drag()/.update_drag()/.finish_drag() quando o modo está armado.
Emite commit_requested(kind, geometry, with_dialog) — main.py liga isso
em NodeFactory.create.
"""

from enum import Enum, auto
from typing import Optional

from PyQt6.QtCore import QObject, QPointF, QRectF, pyqtSignal


class InsertState(Enum):
    IDLE     = auto()
    ARMED    = auto()
    DRAGGING = auto()


class InsertController(QObject):
    state_changed      = pyqtSignal(object)
    armed_kind_changed = pyqtSignal(object)
    drag_updated       = pyqtSignal(QRectF)
    commit_requested   = pyqtSignal(str, QRectF, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = InsertState.IDLE
        self._kind: Optional[str] = None
        self._with_dialog = False
        self._drag_origin: Optional[QPointF] = None
        self._drag_current: Optional[QPointF] = None

    @property
    def state(self): return self._state
    @property
    def armed_kind(self): return self._kind
    @property
    def with_dialog(self): return self._with_dialog
    @property
    def drag_origin(self): return self._drag_origin

    def arm(self, kind: str, with_dialog: bool = False):
        if self._state != InsertState.IDLE and self._kind == kind and self._with_dialog == with_dialog:
            self.disarm()
            return
        self._kind = kind
        self._with_dialog = with_dialog
        self._set_state(InsertState.ARMED)
        self.armed_kind_changed.emit(kind)

    def disarm(self):
        self._kind = None
        self._with_dialog = False
        self._drag_origin = None
        self._drag_current = None
        self._set_state(InsertState.IDLE)
        self.armed_kind_changed.emit(None)

    def start_drag(self, scene_pos: QPointF):
        if self._state != InsertState.ARMED:
            return
        self._drag_origin = QPointF(scene_pos)
        self._drag_current = QPointF(scene_pos)
        self._set_state(InsertState.DRAGGING)
        self.drag_updated.emit(self._current_rect())

    def update_drag(self, scene_pos: QPointF):
        if self._state != InsertState.DRAGGING:
            return
        self._drag_current = QPointF(scene_pos)
        self.drag_updated.emit(self._current_rect())

    def finish_drag(self, scene_pos: QPointF):
        if self._state != InsertState.DRAGGING:
            return
        self._drag_current = QPointF(scene_pos)
        rect = self._current_rect()
        kind = self._kind
        with_dialog = self._with_dialog
        self.disarm()
        self.commit_requested.emit(kind, rect, with_dialog)

    def _current_rect(self) -> QRectF:
        a, b = self._drag_origin, self._drag_current
        x, y = min(a.x(), b.x()), min(a.y(), b.y())
        w, h = abs(b.x() - a.x()), abs(b.y() - a.y())
        return QRectF(x, y, w, h)

    def _set_state(self, new_state):
        if new_state != self._state:
            self._state = new_state
            self.state_changed.emit(new_state)

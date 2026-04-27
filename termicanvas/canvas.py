"""CanvasView (infinito, zoom/pan) + CanvasNav (overlay de navegacao)."""

from PyQt6.QtCore import QEvent, QPointF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsItem,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QWidget,
)

from .agent import AgentWidget
from .icons import get_icon
from .node import NodeFrame
from .terminal import TerminalWidget
from .tokens import (
    ACCENT,
    BG_CANVAS,
    BG_ELEVATED,
    BG_SIDEBAR,
    BG_SURFACE,
    BG_TERMINAL,
    BORDER,
    BORDER_HOVER,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from .widgets import PromptCard


class CanvasView(QGraphicsView):
    nodes_changed             = pyqtSignal()
    new_terminal_requested    = pyqtSignal()
    debug_monitor_requested   = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene()
        self._scene.setSceneRect(-50000, -50000, 100000, 100000)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor(BG_CANVAS)))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)

        self._panning    = False
        self._pan_start  = None
        self._space_held = False

        self.proxies       = []
        self.focused_frame = None

        self.connections  = []   # [(src_frame, tgt_frame), ...]
        self._connecting  = False
        self._conn_source = None
        self._conn_mouse  = QPointF(0, 0)

        QApplication.instance().installEventFilter(self)

        # overlay de navegação — posicionado em resizeEvent
        self._nav = CanvasNav(self)
        self._nav.raise_()

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor(BG_CANVAS))
        scale = self.transform().m11()

        step = 40
        if scale < 0.25:
            step = 160
        elif scale < 0.5:
            step = 80

        left = int(rect.left()) - (int(rect.left()) % step)
        top  = int(rect.top())  - (int(rect.top())  % step)

        pen_thin = QPen(QColor(255, 255, 255, 14))
        pen_thin.setWidth(0)
        painter.setPen(pen_thin)
        x = left
        while x < rect.right():
            if int((x - left) / step) % 5 != 0:
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += step
        y = top
        while y < rect.bottom():
            if int((y - top) / step) % 5 != 0:
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += step

        pen_bold = QPen(QColor(255, 255, 255, 28))
        pen_bold.setWidth(0)
        painter.setPen(pen_bold)
        x = left
        while x < rect.right():
            if int((x - left) / step) % 5 == 0:
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += step
        y = top
        while y < rect.bottom():
            if int((y - top) / step) % 5 == 0:
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += step

    def drawForeground(self, painter, rect):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        PORT_R = 7

        # conexões estabelecidas
        for src_frame, tgt_frame in self.connections:
            src_proxy = next((p for p, f in self.proxies if f is src_frame), None)
            tgt_proxy = next((p for p, f in self.proxies if f is tgt_frame), None)
            if src_proxy is None or tgt_proxy is None:
                continue
            p1 = self._port_scene_pos(src_proxy, src_frame, "out")
            p2 = self._port_scene_pos(tgt_proxy, tgt_frame, "in")
            cx = (p1.x() + p2.x()) / 2
            path = QPainterPath(p1)
            path.cubicTo(QPointF(cx, p1.y()), QPointF(cx, p2.y()), p2)
            pen = QPen(QColor(ACCENT), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        # linha rubber-band durante modo conexão
        if self._connecting and self._conn_source is not None:
            src_proxy = next((p for p, f in self.proxies if f is self._conn_source), None)
            if src_proxy is not None:
                p1 = self._port_scene_pos(src_proxy, self._conn_source, "out")
                cx = (p1.x() + self._conn_mouse.x()) / 2
                path = QPainterPath(p1)
                path.cubicTo(
                    QPointF(cx, p1.y()),
                    QPointF(cx, self._conn_mouse.y()),
                    self._conn_mouse,
                )
                pen = QPen(QColor(ACCENT), 2)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

        # portas IN (sinks: agent, terminal)
        for proxy, frame in self._sink_proxies():
            pos = self._port_scene_pos(proxy, frame, "in")
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(QBrush(QColor(SUCCESS)))
            painter.drawEllipse(pos, PORT_R, PORT_R)

        # portas OUT (sources: agent, prompt card)
        for proxy, frame in self._source_proxies():
            pos = self._port_scene_pos(proxy, frame, "out")
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(QBrush(QColor(ACCENT)))
            painter.drawEllipse(pos, PORT_R, PORT_R)

    def _source_proxies(self):
        return [(p, f) for p, f in self.proxies if isinstance(f.inner, (AgentWidget, PromptCard))]

    def _sink_proxies(self):
        return [(p, f) for p, f in self.proxies if isinstance(f.inner, (AgentWidget, TerminalWidget))]

    def _port_scene_pos(self, proxy, frame, side):
        pos = proxy.pos()
        y   = pos.y() + frame.height() / 2
        if side == "out":
            return QPointF(pos.x() + frame.width(), y)
        return QPointF(pos.x(), y)

    def _port_hit(self, scene_pos, proxy, frame, side, radius=14):
        port = self._port_scene_pos(proxy, frame, side)
        dx   = scene_pos.x() - port.x()
        dy   = scene_pos.y() - port.y()
        return (dx * dx + dy * dy) <= radius * radius

    def start_connection(self, frame):
        self._connecting  = True
        self._conn_source = frame
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def finish_connection(self, target_frame):
        if self._conn_source is target_frame:
            self.cancel_connection()
            return
        self.connections = [(s, t) for s, t in self.connections if s is not self._conn_source]
        self.connections.append((self._conn_source, target_frame))
        self.cancel_connection()

    def cancel_connection(self):
        self._connecting  = False
        self._conn_source = None
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self._scene.update()

    def add_node(self, inner_widget, title, size=(720, 460), icon=""):
        frame = NodeFrame(title, inner_widget, icon=icon)
        frame.resize(*size)

        proxy = self._scene.addWidget(frame)
        proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        center = self.mapToScene(self.viewport().rect().center())
        offset = len(self.proxies) * 30
        proxy.setPos(center.x() - size[0] / 2 + offset, center.y() - size[1] / 2 + offset)

        frame.header.drag_moved.connect(lambda d, p=proxy: self._drag(p, d))
        frame.header.focus_requested.connect(lambda f=frame: self._focus(f))
        frame.header.close_clicked.connect(lambda f=frame: self._close(f))
        frame.header.title_changed.connect(lambda t, f=frame: self.nodes_changed.emit())
        frame.grip.resize_moved.connect(lambda d, f=frame, p=proxy: self._resize_frame(f, p, d))
        if hasattr(inner_widget, "_schedule_resize"):
            frame.resized.connect(lambda _sz, w=inner_widget: w._schedule_resize())

        if isinstance(inner_widget, TerminalWidget):
            frame.header.show_font_controls()
            frame.header.font_up_clicked.connect(inner_widget.font_up)
            frame.header.font_down_clicked.connect(inner_widget.font_down)
            frame.header.color_picked.connect(
                lambda c, f=frame: f.set_node_color(c, custom=True)
            )
        elif isinstance(inner_widget, (AgentWidget, PromptCard)):
            frame.header.color_btn.show()
            frame.header.color_picked.connect(
                lambda c, f=frame: f.set_node_color(c, custom=True)
            )

        self.proxies.append((proxy, frame))
        self._focus(frame)
        inner_widget.setFocus()
        self.nodes_changed.emit()
        return frame

    GRID_STEP = 40

    def _drag(self, proxy, delta):
        scale = self.transform().m11()
        new_x = proxy.pos().x() + delta.x() / scale
        new_y = proxy.pos().y() + delta.y() / scale
        if not self._alt_held():
            new_x = round(new_x / self.GRID_STEP) * self.GRID_STEP
            new_y = round(new_y / self.GRID_STEP) * self.GRID_STEP
        proxy.setPos(new_x, new_y)

    def _resize_frame(self, frame, proxy, delta):
        scale = self.transform().m11()
        new_w = max(260, int(frame.width()  + delta.x() / scale))
        new_h = max(180, int(frame.height() + delta.y() / scale))
        if not self._alt_held():
            new_w = max(260, round(new_w / self.GRID_STEP) * self.GRID_STEP)
            new_h = max(180, round(new_h / self.GRID_STEP) * self.GRID_STEP)
        frame.resize(new_w, new_h)

    def _alt_held(self):
        return bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)

    def _focus(self, frame):
        for proxy, f in self.proxies:
            f.set_focused(f is frame)
            proxy.setZValue(1 if f is frame else 0)
        self.focused_frame = frame
        if frame is not None:
            frame.inner.setFocus(Qt.FocusReason.OtherFocusReason)
        self.nodes_changed.emit()

    def _close(self, frame):
        # Late import to avoid pulling monitor (and psutil) at module load
        from .monitor import DebugMonitorWidget

        for i, (proxy, f) in enumerate(self.proxies):
            if f is frame:
                inner = frame.inner
                if isinstance(inner, TerminalWidget):
                    node_id = inner.node_id
                    if node_id and getattr(self, "_bus_ref", None):
                        self._bus_ref.unregister(node_id)
                    inner.shutdown()
                elif isinstance(inner, DebugMonitorWidget):
                    inner.shutdown()
                self._scene.removeItem(proxy)
                del self.proxies[i]
                if self.focused_frame is frame:
                    self.focused_frame = None
                break
        self.connections = [(s, t) for s, t in self.connections if s is not frame and t is not frame]
        self.nodes_changed.emit()

    def focus_and_center(self, frame):
        for proxy, f in self.proxies:
            if f is frame:
                self._focus(frame)
                self.centerOn(proxy)
                break

    def wheelEvent(self, event):
        view_pos = event.position().toPoint()
        item     = self.itemAt(view_pos)

        if isinstance(item, QGraphicsProxyWidget):
            widget = item.widget()
            if isinstance(widget, NodeFrame):
                if isinstance(widget.inner, TerminalWidget) and (
                    event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                ):
                    terminal = widget.inner
                    if event.angleDelta().y() > 0:
                        terminal.screen.prev_page()
                    else:
                        terminal.screen.next_page()
                    terminal._render()
                    event.accept()
                    return
                inner = widget.inner
                if isinstance(inner, (QPlainTextEdit, QTextEdit)):
                    sb    = inner.verticalScrollBar()
                    delta = event.angleDelta().y()
                    step  = max(1, sb.singleStep()) * 3
                    sb.setValue(sb.value() - int(delta / 120 * step))
            event.accept()
            return

        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        scale  = self.transform().m11() * factor
        if 0.15 <= scale <= 4.0:
            self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._space_held
        ):
            self._panning   = True
            self._pan_start = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())

            # modo conexão: procura porta de entrada num sink (agent/terminal)
            if self._connecting:
                for proxy, frame in self._sink_proxies():
                    if frame is not self._conn_source and self._port_hit(scene_pos, proxy, frame, "in"):
                        self.finish_connection(frame)
                        event.accept()
                        return
                self.cancel_connection()
                event.accept()
                return

            # verifica clique em porta de saída (source: agent/prompt) → inicia conexão
            for proxy, frame in self._source_proxies():
                if self._port_hit(scene_pos, proxy, frame, "out"):
                    self.start_connection(frame)
                    event.accept()
                    return

            item = self.itemAt(event.position().toPoint())
            if item is None:
                # Clique no fundo do canvas: tira o foco de qualquer node
                # (indicador de idle/ativo segue o foco) + inicia pan
                self._focus(None)
                self._panning   = True
                self._pan_start = event.position().toPoint()
                self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
            if isinstance(item, QGraphicsProxyWidget):
                widget = item.widget()
                if isinstance(widget, NodeFrame):
                    self._focus(widget)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            pos   = event.position().toPoint()
            delta = pos - self._pan_start
            self._pan_start = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()   - delta.y())
            event.accept()
            return
        if self._connecting:
            self._conn_mouse = self.mapToScene(event.position().toPoint())
            self._scene.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.viewport().setCursor(
                Qt.CursorShape.OpenHandCursor if self._space_held else Qt.CursorShape.ArrowCursor
            )
            event.accept()
            if self.focused_frame is not None:
                self.focused_frame.inner.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event):
        et = event.type()
        if et == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            return False
        if et == QEvent.Type.KeyRelease and event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            if not self._panning:
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            return False
        if et == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            if self._connecting:
                self.cancel_connection()
                return True
        if et == QEvent.Type.KeyPress:
            mods = event.modifiers()
            key  = event.key()
            ctrl_only = mods == Qt.KeyboardModifier.ControlModifier
            if ctrl_only and key == Qt.Key.Key_T:
                self.new_terminal_requested.emit()
                return True
            if ctrl_only and key == Qt.Key.Key_W:
                if self.focused_frame is not None:
                    self._close(self.focused_frame)
                return True
            if ctrl_only and key == Qt.Key.Key_Tab:
                self._focus_next()
                return True
            if (mods == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                    and key == Qt.Key.Key_D):
                self.debug_monitor_requested.emit()
                return True
            # Alt + 1..9 — foca o N-esimo terminal (ordem da topbar)
            if mods == Qt.KeyboardModifier.AltModifier:
                if Qt.Key.Key_1.value <= key <= Qt.Key.Key_9.value:
                    idx = key - Qt.Key.Key_1.value
                    terminals = [f for _, f in self.proxies if isinstance(f.inner, TerminalWidget)]
                    if 0 <= idx < len(terminals):
                        self.focus_and_center(terminals[idx])
                        return True
        return False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scene.update()
        margin = 12
        self._nav.move(
            self.width()  - self._nav.width()  - margin,
            self.height() - self._nav.height() - margin,
        )

    def _focus_next(self):
        if not self.proxies:
            return
        frames = [f for _, f in self.proxies]
        if self.focused_frame in frames:
            idx = frames.index(self.focused_frame)
            nxt = frames[(idx + 1) % len(frames)]
        else:
            nxt = frames[0]
        self.focus_and_center(nxt)

    def reset_view(self):
        self.resetTransform()
        self.centerOn(0, 0)

    def fit_all(self):
        if not self.proxies:
            self.reset_view()
            return
        rect = self._scene.itemsBoundingRect()
        rect.adjust(-120, -120, 120, 120)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_in(self):
        if self.transform().m11() < 4.0:
            self.scale(1.2, 1.2)

    def zoom_out(self):
        if self.transform().m11() > 0.15:
            self.scale(1 / 1.2, 1 / 1.2)


class CanvasNav(QWidget):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.setObjectName("cannav")
        self._accent_color = ACCENT
        self._buttons = []
        self.setStyleSheet(f"""
            #cannav {{
                background: {BG_SIDEBAR};
                border: 1px solid {BORDER};
                border-radius: 2px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        nav_specs = [
            ("minus",  "Zoom out",       canvas.zoom_out,   None),
            ("plus",   "Zoom in",        canvas.zoom_in,    None),
            (None,     "Resetar zoom",   canvas.reset_view, "1:1"),
            ("square", "Encaixar tudo",  canvas.fit_all,    None),
        ]
        for icon_name, tooltip, slot, text in nav_specs:
            b = QPushButton(text or "")
            b.setFixedSize(32, 32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(tooltip)
            if icon_name:
                b.setIcon(get_icon(icon_name, color=TEXT_SECONDARY, size=14))
                b.setIconSize(QSize(14, 14))
            b.clicked.connect(slot)
            self._buttons.append(b)
            layout.addWidget(b)

        self._apply_button_style()
        self.adjustSize()
        self.raise_()

    def _apply_button_style(self):
        hover_border = self._accent_color
        style = f"""
            QPushButton {{
                background: {BG_ELEVATED}; color: {TEXT_SECONDARY};
                border: 1px solid {BORDER}; border-radius: 2px;
                font-size: 11pt; font-weight: 500;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY}; border-color: {hover_border};
                background: {BG_SURFACE};
            }}
            QPushButton:pressed {{ background: {BG_TERMINAL}; }}
        """
        for b in self._buttons:
            b.setStyleSheet(style)

    def set_accent(self, color):
        self._accent_color = color
        self._apply_button_style()

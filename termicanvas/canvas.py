"""CanvasView (infinito, zoom/pan) + CanvasNav (overlay de navegacao)."""

from math import hypot

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsItem,
    QGraphicsProxyWidget,
    QGraphicsRectItem,
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
    insert_press              = pyqtSignal(QPointF)
    insert_move               = pyqtSignal(QPointF)
    insert_release            = pyqtSignal(QPointF)
    insert_escape             = pyqtSignal()
    island_center_requested   = pyqtSignal()

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
        # Cor de destaque atual — usada pra pintar a borda do node focado.
        # MainWindow sincroniza via set_accent() ao mudar a accent global.
        self._accent_color = ACCENT
        # Modo de tema: False = dark (fundo preto + grid branco com alpha),
        # True = light (fundo branco + grid preto com alpha). Toggle vem da
        # topbar via set_light_mode().
        self._light_mode = False

        self.connections  = []   # [(src_frame, tgt_frame), ...] — Prompt/Agent edges
        self._connecting  = False
        self._conn_source = None
        self._conn_mouse  = QPointF(0, 0)
        # Chains: parentesco entre orquestrador e agente spawnado. Desenhadas
        # como catenaria (linha curva afundando por gravidade) ligando o
        # bottom-center do pai ao top-center do filho.
        self.chains       = []   # [(parent_frame, child_frame), ...]
        # Modo de criar chain manualmente — ativado pelo botao no header.
        self._chaining     = False
        self._chain_source = None
        self._chain_mouse  = QPointF(0, 0)
        # Per-drag virtual position/size state — keeps the unsnapped target
        # so the cursor can accumulate sub-grid motion without the node
        # getting stuck inside a single cell.
        self._virtual_pos: dict = {}    # proxy -> QPointF
        self._virtual_size: dict = {}   # frame -> (float w, float h)

        # Insert mode (driven externally by InsertController)
        self._insert_active = False
        self._drag_preview: QGraphicsRectItem | None = None

        QApplication.instance().installEventFilter(self)

        # overlay de navegação — posicionado em resizeEvent
        self._nav = CanvasNav(self)
        self._nav.raise_()

    def set_light_mode(self, enabled: bool):
        """Alterna entre modo dark (fundo preto + grid branco) e light (fundo
        branco + grid preto). Atualiza tanto o brush base (usado fora do dirty
        rect) quanto invalida a scene para forcar repaint do grid em zoom."""
        self._light_mode = bool(enabled)
        bg = "#ffffff" if self._light_mode else BG_CANVAS
        self.setBackgroundBrush(QBrush(QColor(bg)))
        self._scene.invalidate(self._scene.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)
        self.viewport().update()
        # Propaga pro nav (toolbar de zoom no canto inferior direito)
        if hasattr(self, "_nav") and self._nav is not None:
            self._nav.set_light_mode(self._light_mode)
        # Propaga pros nodes (atualiza cor do icone do tipo no header)
        for _proxy, frame in self.proxies:
            frame.set_light_mode(self._light_mode)

    def is_light_mode(self) -> bool:
        return self._light_mode

    def drawBackground(self, painter, rect):
        # No light mode usa fundo branco + linhas pretas; no dark, o oposto.
        # Alpha do grid eh BEM maior em light porque linha preta antialias em
        # fundo branco com alpha baixo fica praticamente invisivel.
        if self._light_mode:
            bg = QColor("#ffffff")
            line_rgb = (0, 0, 0)
            alpha_thin = 60
            alpha_bold = 110
        else:
            bg = QColor(BG_CANVAS)
            line_rgb = (255, 255, 255)
            alpha_thin = 14
            alpha_bold = 28

        painter.fillRect(rect, bg)
        scale = self.transform().m11()

        step = 40
        if scale < 0.25:
            step = 160
        elif scale < 0.5:
            step = 80

        left = int(rect.left()) - (int(rect.left()) % step)
        top  = int(rect.top())  - (int(rect.top())  % step)

        r, g, b = line_rgb
        pen_thin = QPen(QColor(r, g, b, alpha_thin))
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

        pen_bold = QPen(QColor(r, g, b, alpha_bold))
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

        # Sombra externa dos nodes (estilo janela macOS).
        # QGraphicsDropShadowEffect quebra QPlainTextEdit em proxy widget — ja
        # foi tentado e revertido. Aqui pintamos 4 camadas concentricas com
        # alpha decrescente direto no background da scene, antes dos items
        # serem renderizados em cima. Custo despresivel (~0.1ms por node).
        painter.setPen(Qt.PenStyle.NoPen)
        # (expansao, alpha) — de fora (mais difusa) pra dentro (mais opaca).
        # Light mode com alpha minimo pra parecer dropshadow sutil de macOS;
        # qualquer coisa maior vira halo escuro feio em fundo branco.
        if self._light_mode:
            shadow_layers = ((18, 2), (12, 4), (7, 8), (3, 14))
        else:
            shadow_layers = ((18, 12), (12, 22), (7, 40), (3, 70))
        offset_y = 8
        radius = 10
        for proxy, frame in self.proxies:
            pos = proxy.pos()
            w, h = frame.width(), frame.height()
            # Skip se o node estiver fora do rect visivel (otimizacao)
            node_rect = QRectF(pos.x(), pos.y(), w, h)
            if not rect.intersects(node_rect.adjusted(-20, -20, 20, 28)):
                continue
            for expand, alpha in shadow_layers:
                shadow_rect = QRectF(
                    pos.x() - expand,
                    pos.y() - expand + offset_y,
                    w + 2 * expand,
                    h + 2 * expand,
                )
                painter.setBrush(QBrush(QColor(0, 0, 0, alpha)))
                painter.drawRoundedRect(shadow_rect, radius + expand, radius + expand)

    def add_chain(self, parent_frame, child_frame):
        """Adiciona um link de parentesco (orquestrador -> agente spawnado).
        Evita duplicatas se o mesmo par ja existir."""
        if parent_frame is None or child_frame is None:
            return
        if parent_frame is child_frame:
            return
        for p, c in self.chains:
            if p is parent_frame and c is child_frame:
                return
        self.chains.append((parent_frame, child_frame))
        self._scene.invalidate(self._scene.sceneRect(), QGraphicsScene.SceneLayer.ForegroundLayer)

    def start_chain(self, frame):
        """Entra em modo de criacao manual de chain. O proximo clique em outro
        frame cria a corrente. Esc cancela."""
        self._chaining = True
        self._chain_source = frame
        self._chain_mouse = QPointF(0, 0)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def finish_chain(self, target_frame):
        if self._chain_source is None or target_frame is None:
            self.cancel_chain()
            return
        if target_frame is self._chain_source:
            self.cancel_chain()
            return
        self.add_chain(self._chain_source, target_frame)
        self.cancel_chain()

    def cancel_chain(self):
        self._chaining = False
        self._chain_source = None
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self._scene.update()

    @staticmethod
    def _pick_chain_anchors(parent_rect, child_rect):
        """Escolhe pontos de saida e entrada conforme posicao relativa dos
        bboxes. Retorna (p1, dir1, p2, dir2) onde dir e uma das strings
        'right'/'left'/'down'/'up'.

        Direcao dominante: se distancia horizontal > vertical, usa laterais;
        senao, usa top/bottom. Isso produz curvas em S naturais.
        """
        pc = parent_rect.center()
        cc = child_rect.center()
        dx = cc.x() - pc.x()
        dy = cc.y() - pc.y()

        if abs(dx) > abs(dy):
            if dx > 0:
                # Child a direita do pai
                p1 = QPointF(parent_rect.right(), pc.y())
                p2 = QPointF(child_rect.left(), cc.y())
                return p1, "right", p2, "left"
            else:
                # Child a esquerda do pai
                p1 = QPointF(parent_rect.left(), pc.y())
                p2 = QPointF(child_rect.right(), cc.y())
                return p1, "left", p2, "right"
        else:
            if dy >= 0:
                # Child abaixo do pai (caso comum no spawn)
                p1 = QPointF(pc.x(), parent_rect.bottom())
                p2 = QPointF(cc.x(), child_rect.top())
                return p1, "down", p2, "up"
            else:
                # Child acima do pai
                p1 = QPointF(pc.x(), parent_rect.top())
                p2 = QPointF(cc.x(), child_rect.bottom())
                return p1, "up", p2, "down"

    @staticmethod
    def _offset_in_direction(point, direction, dist):
        """Retorna ponto deslocado `dist` unidades na direcao indicada."""
        if direction == "right":
            return QPointF(point.x() + dist, point.y())
        if direction == "left":
            return QPointF(point.x() - dist, point.y())
        if direction == "down":
            return QPointF(point.x(), point.y() + dist)
        if direction == "up":
            return QPointF(point.x(), point.y() - dist)
        return QPointF(point)

    def _draw_chain(self, painter, parent_proxy, parent_frame, child_proxy, child_frame):
        """Desenha 1 chain como curva-S tracejada conectando o lado mais
        proximo do parent ao lado mais proximo do child. Detecta obstaculos
        no caminho e empurra control points perpendicularmente pra contornar
        por fora (nao por baixo, como catenaria)."""
        from math import hypot

        parent_rect = QRectF(
            parent_proxy.pos().x(), parent_proxy.pos().y(),
            parent_frame.width(), parent_frame.height(),
        )
        child_rect = QRectF(
            child_proxy.pos().x(), child_proxy.pos().y(),
            child_frame.width(), child_frame.height(),
        )
        p1, dir1, p2, dir2 = self._pick_chain_anchors(parent_rect, child_rect)

        # Coleta obstaculos (todos os outros frames). Pra cubic-S a bbox de
        # intersecao pode ser qualquer direcao — nao filtra por X.
        obstacles = []
        for proxy, frame in self.proxies:
            if frame is parent_frame or frame is child_frame:
                continue
            rect = QRectF(proxy.pos().x(), proxy.pos().y(), frame.width(), frame.height())
            obstacles.append(rect.adjusted(-5, -5, 5, 5))

        # Offset proporcional a distancia — control points "empurram" pra fora
        # do node na direcao de saida/entrada, criando curva em S suave.
        dist = hypot(p2.x() - p1.x(), p2.y() - p1.y())
        base_offset = max(50.0, dist * 0.35)

        # Perpendicular usado pra desviar de obstaculos. Se routing eh horizontal
        # (right/left), perpendicular eh vertical; se vertical, perpendicular eh
        # horizontal.
        perp_dir = "down" if dir1 in ("right", "left") else "right"
        perp_offset = 0.0

        path = QPainterPath(p1)
        for _attempt in range(8):
            ctrl1 = self._offset_in_direction(p1, dir1, base_offset)
            ctrl2 = self._offset_in_direction(p2, dir2, base_offset)
            if perp_offset:
                ctrl1 = self._offset_in_direction(ctrl1, perp_dir, perp_offset)
                ctrl2 = self._offset_in_direction(ctrl2, perp_dir, perp_offset)
            path = QPainterPath(p1)
            path.cubicTo(ctrl1, ctrl2, p2)

            # Amostra 30 pontos; se algum cai dentro de obstaculo, empurra
            # perpendicularmente e tenta de novo.
            collides = False
            for i in range(1, 30):
                t = i / 30
                pt = path.pointAtPercent(t)
                for rect in obstacles:
                    if rect.contains(pt):
                        collides = True
                        break
                if collides:
                    break
            if not collides:
                break
            perp_offset += 50  # empurra mais pra fora a cada iteracao

        # Estilo igual da referencia: tracejado fino e sutil.
        if self._light_mode:
            line_color = QColor(80, 80, 80, 170)
        else:
            line_color = QColor(200, 200, 200, 150)
        pen = QPen(line_color, 1.5)
        pen.setDashPattern([4.0, 4.0])
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def drawForeground(self, painter, rect):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        PORT_R = 7

        # Chains de spawn (orquestrador -> filho), pintadas ANTES das connections
        # de prompt/agent — ficam visualmente "atras" das edges semanticas.
        for parent_frame, child_frame in self.chains:
            parent_proxy = next((p for p, f in self.proxies if f is parent_frame), None)
            child_proxy  = next((p for p, f in self.proxies if f is child_frame), None)
            if parent_proxy is None or child_proxy is None:
                continue
            self._draw_chain(painter, parent_proxy, parent_frame, child_proxy, child_frame)

        # Rubber-band durante modo de chain manual: curva S tracejada do
        # lado mais proximo do source ate o cursor.
        if self._chaining and self._chain_source is not None:
            src_proxy = next((p for p, f in self.proxies if f is self._chain_source), None)
            if src_proxy is not None:
                from math import hypot
                # Cria um rect virtual de 1x1 no cursor pra reusar _pick_chain_anchors.
                src_rect = QRectF(
                    src_proxy.pos().x(), src_proxy.pos().y(),
                    self._chain_source.width(), self._chain_source.height(),
                )
                cursor_rect = QRectF(
                    self._chain_mouse.x() - 1, self._chain_mouse.y() - 1, 2, 2,
                )
                p1, dir1, p2, dir2 = self._pick_chain_anchors(src_rect, cursor_rect)
                dist = hypot(p2.x() - p1.x(), p2.y() - p1.y())
                base_offset = max(50.0, dist * 0.35)
                ctrl1 = self._offset_in_direction(p1, dir1, base_offset)
                ctrl2 = self._offset_in_direction(p2, dir2, base_offset)
                path = QPainterPath(p1)
                path.cubicTo(ctrl1, ctrl2, p2)
                line_color = QColor(80, 80, 80, 170) if self._light_mode else QColor(200, 200, 200, 150)
                pen = QPen(line_color, 1.5)
                pen.setDashPattern([4.0, 4.0])
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

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

    def set_accent(self, color):
        """Atualiza a accent que sera usada em nodes novos e refletida na
        borda dos ja existentes. MainWindow chama isso em sync com a topbar."""
        self._accent_color = color

    def add_node(self, inner_widget, title, size=(720, 460), icon=""):
        frame = NodeFrame(title, inner_widget, icon=icon)
        frame.resize(*size)
        # Aplica a accent global antes de inserir, garantindo que nodes novos
        # nascam com a cor atual em vez do ACCENT default hardcoded.
        frame.set_node_color(self._accent_color)
        # Aplica o tema atual para que o icone do tipo no header nasca na
        # cor certa (escuro em fundo claro, claro em fundo escuro).
        frame.set_light_mode(self._light_mode)

        proxy = self._scene.addWidget(frame)
        proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        center = self.mapToScene(self.viewport().rect().center())
        offset = len(self.proxies) * 30
        proxy.setPos(center.x() - size[0] / 2 + offset, center.y() - size[1] / 2 + offset)

        frame.header.drag_moved.connect(lambda d, p=proxy: self._drag(p, d))
        frame.header.drag_finished.connect(lambda p=proxy: self._drag_end(p))
        frame.header.focus_requested.connect(lambda f=frame: self._focus(f))
        frame.header.close_clicked.connect(lambda f=frame: self._close(f))
        frame.header.title_changed.connect(lambda t, f=frame: self.nodes_changed.emit())
        frame.grip.resize_moved.connect(lambda d, f=frame, p=proxy: self._resize_frame(f, p, d))
        frame.grip.resize_finished.connect(lambda f=frame: self._resize_end(f))
        if hasattr(inner_widget, "_schedule_resize"):
            frame.resized.connect(lambda _sz, w=inner_widget: w._schedule_resize())

        if isinstance(inner_widget, TerminalWidget):
            frame.header.show_font_controls()
            frame.header.font_up_clicked.connect(inner_widget.font_up)
            frame.header.font_down_clicked.connect(inner_widget.font_down)

        self.proxies.append((proxy, frame))
        self._focus(frame)
        inner_widget.setFocus()
        self.nodes_changed.emit()
        return frame

    GRID_STEP = 40

    def _drag(self, proxy, delta):
        """Move livre durante drag — sem snap em tempo real (evita teleporte
        no primeiro pixel + jitter). Snap acontece no _drag_end."""
        scale = self.transform().m11()
        if proxy not in self._virtual_pos:
            self._virtual_pos[proxy] = QPointF(proxy.pos())
        self._virtual_pos[proxy] += QPointF(delta.x() / scale, delta.y() / scale)
        proxy.setPos(self._virtual_pos[proxy])

    def _drag_end(self, proxy):
        """Snapa pra posicao mais proxima do grid — a menos que Alt esteja
        segurado, caso em que mantem a posicao livre."""
        virt = self._virtual_pos.pop(proxy, None)
        if virt is not None and not self._alt_held():
            sx = round(virt.x() / self.GRID_STEP) * self.GRID_STEP
            sy = round(virt.y() / self.GRID_STEP) * self.GRID_STEP
            proxy.setPos(sx, sy)

    def _resize_frame(self, frame, proxy, delta):
        """Resize livre durante drag — snap acontece no _resize_end."""
        scale = self.transform().m11()
        if frame not in self._virtual_size:
            self._virtual_size[frame] = (float(frame.width()), float(frame.height()))
        vw, vh = self._virtual_size[frame]
        vw += delta.x() / scale
        vh += delta.y() / scale
        self._virtual_size[frame] = (vw, vh)
        frame.resize(max(260, int(vw)), max(180, int(vh)))

    def _resize_end(self, frame):
        """Snapa o tamanho final pro grid — exceto se Alt segurado."""
        size = self._virtual_size.pop(frame, None)
        if size is not None and not self._alt_held():
            vw, vh = size
            new_w = max(260, round(vw / self.GRID_STEP) * self.GRID_STEP)
            new_h = max(180, round(vh / self.GRID_STEP) * self.GRID_STEP)
            frame.resize(new_w, new_h)

    def _alt_held(self):
        return bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)

    # ---------- Insert mode (driven by InsertController) ----------

    def set_insert_active(self, active: bool):
        """Liga/desliga modo de inserção. Quando ativo, cliques no canvas
        emitem insert_press/insert_move/insert_release ao invés de pan/foco."""
        self._insert_active = bool(active)
        if active:
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self.clear_drag_preview()

    def show_drag_preview(self, scene_rect: QRectF):
        """Mostra/atualiza retângulo translúcido durante DRAGGING (snap 40px)."""
        snapped = self._snap_rect(scene_rect)
        if self._drag_preview is None:
            self._drag_preview = QGraphicsRectItem()
            pen = QPen(QColor(ACCENT), 1.2)
            pen.setStyle(Qt.PenStyle.DashLine)
            self._drag_preview.setPen(pen)
            r, g, b = self._accent_rgb()
            self._drag_preview.setBrush(QBrush(QColor(r, g, b, 26)))
            self._drag_preview.setZValue(9999)
            self._scene.addItem(self._drag_preview)
        self._drag_preview.setRect(snapped)

    def clear_drag_preview(self):
        if self._drag_preview is not None:
            self._scene.removeItem(self._drag_preview)
            self._drag_preview = None

    def _snap_rect(self, rect: QRectF) -> QRectF:
        if self._alt_held():
            return rect
        step = self.GRID_STEP
        x = round(rect.x() / step) * step
        y = round(rect.y() / step) * step
        w = round(rect.width() / step) * step
        h = round(rect.height() / step) * step
        return QRectF(x, y, w, h)

    def _accent_rgb(self):
        c = QColor(ACCENT)
        return (c.red(), c.green(), c.blue())

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
                frame.deleteLater()
                if hasattr(proxy, "deleteLater"):
                    proxy.deleteLater()
                del self.proxies[i]
                if self.focused_frame is frame:
                    self.focused_frame = None
                break
        self.connections = [(s, t) for s, t in self.connections if s is not frame and t is not frame]
        self.chains = [(p, c) for p, c in self.chains if p is not frame and c is not frame]
        self.nodes_changed.emit()

    def clear_all(self, bus=None):
        """Fecha todos os nodes do canvas.

        Itera uma copia da lista de proxies (a real eh mutada conforme
        cada node sai). Falhas individuais sao silenciadas em diagnostics
        para que um shutdown ruim nao bloqueie os demais.
        """
        from .monitor import DebugMonitorWidget
        from .diagnostics import record_error

        for proxy, frame in list(self.proxies):
            inner = frame.inner
            if isinstance(inner, TerminalWidget):
                node_id = getattr(inner, "node_id", None)
                if node_id and bus is not None:
                    try:
                        bus.unregister(node_id)
                    except Exception as e:
                        record_error("canvas.clear_all.unregister", e)
                try:
                    inner.shutdown()
                except Exception as e:
                    record_error("canvas.clear_all.shutdown", e)
            elif isinstance(inner, DebugMonitorWidget):
                try:
                    inner.shutdown()
                except Exception as e:
                    record_error("canvas.clear_all.monitor_shutdown", e)
            try:
                self._scene.removeItem(proxy)
                frame.deleteLater()
                if hasattr(proxy, "deleteLater"):
                    proxy.deleteLater()
            except Exception as e:
                record_error("canvas.clear_all.scene_remove", e)

        self.proxies.clear()
        self.connections.clear()
        self.chains.clear()
        self.focused_frame = None
        self._virtual_pos.clear()
        self._virtual_size.clear()
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
        if self._insert_active and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            self.insert_press.emit(scene_pos)
            event.accept()
            return
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

            # modo chain: clique em qualquer NodeFrame finaliza a chain
            if self._chaining:
                item = self.itemAt(event.position().toPoint())
                target_frame = None
                if isinstance(item, QGraphicsProxyWidget):
                    widget = item.widget()
                    if isinstance(widget, NodeFrame):
                        target_frame = widget
                if target_frame is not None:
                    self.finish_chain(target_frame)
                else:
                    self.cancel_chain()
                event.accept()
                return

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
        if self._insert_active and event.buttons() & Qt.MouseButton.LeftButton:
            self.insert_move.emit(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
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
        if self._chaining:
            self._chain_mouse = self.mapToScene(event.position().toPoint())
            self._scene.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._insert_active and event.button() == Qt.MouseButton.LeftButton:
            self.insert_release.emit(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
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
        if et == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape and self._insert_active:
            self.insert_escape.emit()
            event.accept()
            return True
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
            if self._chaining:
                self.cancel_chain()
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

    def center_island(self):
        self.island_center_requested.emit()


class CanvasNav(QWidget):
    """Toolbar flutuante de navegacao (zoom/fit/center) no canto inferior
    direito do canvas. Visual identico ao ToolIsland: gradient translucido com
    cantos arredondados pintado no paintEvent (em vez de stylesheet)."""

    HEIGHT = 40

    def __init__(self, canvas):
        super().__init__(canvas)
        self.setObjectName("cannav")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(self.HEIGHT)
        self._accent_color = ACCENT
        self._light_mode = False
        self._buttons = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        nav_specs = [
            ("minus",  "Zoom out",         canvas.zoom_out,      None),
            ("plus",   "Zoom in",          canvas.zoom_in,       None),
            (None,     "Resetar zoom",     canvas.reset_view,    "1:1"),
            ("square", "Encaixar tudo",    canvas.fit_all,       None),
            ("box",    "Centralizar ilha", canvas.center_island, None),
        ]
        for icon_name, tooltip, slot, text in nav_specs:
            b = QPushButton(text or "")
            b.setFixedSize(28, 28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(tooltip)
            if icon_name:
                b.setIcon(get_icon(icon_name, color=TEXT_SECONDARY, size=16))
                b.setIconSize(QSize(16, 16))
            b.clicked.connect(slot)
            self._buttons.append(b)
            layout.addWidget(b)

        self._apply_button_style()
        self.adjustSize()
        self.raise_()

    def _apply_button_style(self):
        # Botoes sem borda, hover sutil — mesmo padrao do IconButton do island.
        icon_color = TEXT_SECONDARY if not self._light_mode else "#4a4a4a"
        hover_bg = "rgba(255, 255, 255, 0.05)" if not self._light_mode else "rgba(0, 0, 0, 0.06)"
        style = f"""
            QPushButton {{
                background: transparent; color: {icon_color};
                border: 1px solid transparent; border-radius: 6px;
                font-size: 10pt; font-weight: 600;
            }}
            QPushButton:hover {{ background: {hover_bg}; }}
        """
        for b in self._buttons:
            b.setStyleSheet(style)
            # Re-renderiza icone com cor adequada ao tema
            icon_name = b.toolTip().split()[0].lower() if not b.text() else None
            # Caminho mais robusto: usar o icon_name guardado se houver
        # Reaplica icones na cor certa (precisa re-mapear pelo tooltip)
        icon_map = {
            "Zoom out":         "minus",
            "Zoom in":          "plus",
            "Encaixar tudo":    "square",
            "Centralizar ilha": "box",
        }
        for b in self._buttons:
            name = icon_map.get(b.toolTip())
            if name:
                b.setIcon(get_icon(name, color=icon_color, size=16))

    def paintEvent(self, _event):
        # Pintura custom: gradient translucido + cantos arredondados, identico
        # ao ToolIsland. paintEvent ignora stylesheet, por isso usamos QPainter.
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 16, 16)

        grad = QLinearGradient(0, 0, 0, rect.height())
        if self._light_mode:
            grad.setColorAt(0.0, QColor(240, 240, 240, 220))
            grad.setColorAt(1.0, QColor(220, 220, 220, 220))
            border_color = QColor(0, 0, 0, 40)
        else:
            grad.setColorAt(0.0, QColor(48, 48, 48, 190))
            grad.setColorAt(1.0, QColor(34, 34, 34, 190))
            border_color = QColor(255, 255, 255, 36)
        p.fillPath(path, grad)

        p.setPen(border_color)
        p.drawPath(path)
        p.end()

    def set_accent(self, color):
        self._accent_color = color
        self._apply_button_style()

    def set_light_mode(self, enabled: bool):
        self._light_mode = bool(enabled)
        self._apply_button_style()
        self.update()

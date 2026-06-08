import math
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QFont
from PySide6.QtCore import Qt, QTimer, QRectF

class GraphRender(QGraphicsView):
    def __init__(self, physics, parent=None):
        super().__init__(parent)
        self.physics = physics
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(QGraphicsView.DontSavePainterState, True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        self.node_items = {}
        self.edge_items = {}
        self.zoom = 1.0

        self.init_items()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16) # ~60 fps

    def init_items(self):
        # Edges first (so they are drawn under nodes)
        for i, edge in enumerate(self.physics.edges):
            a_idx = edge['from']
            b_idx = edge['to']
            a = self.physics.nodes[a_idx]
            b = self.physics.nodes[b_idx]

            line = QGraphicsLineItem()
            pen = QPen(QColor(100, 100, 100, 100))
            pen.setWidth(1)
            line.setPen(pen)
            line.setZValue(-1)

            self.scene_obj.addItem(line)
            self.edge_items[i] = line

        for i, node in enumerate(self.physics.nodes):
            ellipse = QGraphicsEllipseItem()
            r = self.physics.get_node_radius(node)
            ellipse.setRect(-r, -r, 2*r, 2*r)

            color = node.get('color', '#888888')
            brush = QBrush(QColor(color))
            pen = QPen(Qt.NoPen)

            ellipse.setBrush(brush)
            ellipse.setPen(pen)
            ellipse.setZValue(1)

            self.scene_obj.addItem(ellipse)
            self.node_items[i] = {"ellipse": ellipse, "r": r}

    def tick(self):
        # Run physics
        self.physics.simulate(steps=1)

        # Update UI items
        for i, edge in enumerate(self.physics.edges):
            a_idx = edge['from']
            b_idx = edge['to']
            a = self.physics.nodes[a_idx]
            b = self.physics.nodes[b_idx]

            if a.get('hidden') or b.get('hidden'):
                self.edge_items[i].setVisible(False)
            else:
                self.edge_items[i].setVisible(True)
                self.edge_items[i].setLine(a.get('x', 0), a.get('y', 0), b.get('x', 0), b.get('y', 0))

        for i, node in enumerate(self.physics.nodes):
            item_data = self.node_items[i]
            ellipse = item_data['ellipse']

            if node.get('hidden'):
                ellipse.setVisible(False)
            else:
                ellipse.setVisible(True)
                ellipse.setPos(node.get('x', 0), node.get('y', 0))

                # Apply reveal scale if needed
                scale = node.get('_revealScale', 1.0)
                ellipse.setScale(scale)

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)
        self.zoom *= zoom_factor

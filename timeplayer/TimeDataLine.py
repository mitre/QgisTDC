#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

from qgis.core import *
from qgis.PyQt import QtCore

from qgis.PyQt.QtGui import QPen, QPainterPath, QFont
from qgis.PyQt.QtCore import Qt, QPointF

from .TimeDataElement import TimeDataElement

import numpy as np


class TimeDataLine(TimeDataElement):
    def __init__(
        self, geometry, fid, markeridx, canvas, epoch, epochend=None, attr=None
    ):
        super().__init__(epoch, epochend)
        self.path = QPainterPath()
        self.canvas = canvas
        self.geometry = geometry
        self._fid = fid
        self._attr = attr
        self._markeridx = markeridx

    @property
    def fid(self):
        return self._fid

    @property
    def markeridx(self):
        return self._markeridx

    @property
    def geometry(self):
        return self._geometry

    @geometry.setter
    def geometry(self, g):
        self._geometry = []
        if g.isMultipart():
            for part in g.parts():
                lastV = None
                for v in part:
                    vertex = QgsPointXY(v.toQPointF())
                    self._geometry.append(vertex)
        else:
            linegeo = g.asPolyline()
            lastV = None
            for p in linegeo:
                vertex = QgsPointXY(p.toQPointF())
                self._geometry.append(vertex)

    def geometryTransform(self, xform):
        for g in self._geometry:
            p = QgsPoint(g)
            p.transform(xform)
            g.setX(p.x())
            g.setY(p.y())

    def setMarkerIndex(self, m):
        self._markeridx = m

    def geometrypoints(self):
        return self._geometry

    def asQPointF(self):
        qpt = QtCore.QPointF(self.x(), self.y())
        return qpt

    def transform(self, canvas, paintxform=None, label=None):
        self.path = QPainterPath()
        startpoint = None
        for v in self._geometry:
            drawpt = canvas.toCanvasCoordinates(v).toPoint()
            if startpoint:
                self.path.lineTo(drawpt.x(), drawpt.y())
            else:
                startpoint = drawpt
                self.path.moveTo(drawpt.x(), drawpt.y())

    def transformdraw(self, canvas, qp, paintxform, ptmarker, alpha, deco, label=None):
        lastV = None
        startpoint = None
        self.path = QPainterPath()

        for v in self._geometry:
            drawpt = canvas.toCanvasCoordinates(v).toPoint()
            if startpoint:
                self.path.lineTo(drawpt.x(), drawpt.y())
            else:
                startpoint = drawpt
                self.path.moveTo(drawpt.x(), drawpt.y())

        qp.drawPath(self.path)

        if label and self._attr:
            self.drawlabel(qp, deco)

        # Draw a single point in case path is too short to render at current scale
        startpoint = QPointF(self.path.elementAt(0).x, self.path.elementAt(0).y)
        qp.drawPoint(startpoint)

        if deco.drawendpoints:
            # #Draw endpoints of the line with green/red points for start/end of line
            lastelement = self.path.elementCount() - 1
            endpoint = QPointF(
                self.path.elementAt(lastelement).x, self.path.elementAt(lastelement).y
            )

            origpen = qp.pen()
            startpen = QPen(
                Qt.green, origpen.width() + 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin
            )
            endpen = QPen(
                Qt.red, origpen.width() + 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin
            )
            qp.setPen(startpen)
            qp.drawPoint(startpoint)
            qp.setPen(endpen)
            qp.drawPoint(endpoint)
            qp.setPen(origpen)

    def draw(self, canvas, qp, paintxform, ptmarker, alpha, deco, label=None):

        qp.drawPath(self.path)

        # Draw a single point in case path is too short to render at current scale
        startpoint = QPointF(self.path.elementAt(0).x, self.path.elementAt(0).y)
        qp.drawPoint(startpoint)

        if deco.drawendpoints:
            # #Draw endpoints of the line with green/red points for start/end of line
            lastelement = self.path.elementCount() - 1
            endpoint = QPointF(
                self.path.elementAt(lastelement).x, self.path.elementAt(lastelement).y
            )

            origpen = qp.pen()
            startpen = QPen(
                Qt.green, origpen.width() + 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin
            )
            endpen = QPen(
                Qt.red, origpen.width() + 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin
            )
            qp.setPen(startpen)
            qp.drawPoint(startpoint)
            qp.setPen(endpen)
            qp.drawPoint(endpoint)
            qp.setPen(origpen)

        if label and self._attr:
            self.drawlabel(qp, deco)

    def drawlabel(self, qp, deco):

        drawx = self.path.elementAt(0).x
        drawy = self.path.elementAt(0).y

        labelfont = qp.font()
        labelfont.setPointSize(deco.fontsize)
        labelfont.setWeight(QFont.ExtraBold)
        qp.setFont(labelfont)

        drawrect = QtCore.QRectF(drawx + deco.xoffset, drawy + deco.yoffset, 500, 500)
        qp.drawText(drawrect, self._attr)

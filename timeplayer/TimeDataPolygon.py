#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

from qgis.core import *
from qgis.PyQt import QtCore

from qgis.PyQt.QtGui import QPen, QPainterPath, QPolygon, QFont
from qgis.PyQt.QtCore import Qt, QPointF

from .TimeDataElement import TimeDataElement


class TimeDataPolygon(TimeDataElement):
    def __init__(
        self, geometry, fid, markeridx, canvas, epoch, epochend=None, attr=None
    ):
        super().__init__(epoch, epochend)
        self.geometry = geometry
        self._fid = fid
        self._markeridx = markeridx
        self._attr = attr
        self.poly = []

    @property
    def fid(self):
        return self._fid

    @property
    def markeridx(self):
        return self._markeridx

    @property
    def geometry(self):
        return self._geometry

    @property
    def attr(self):
        return self._attr

    @geometry.setter
    def geometry(self, g):
        self._geometry = []
        if g.isMultipart():
            mp = g.asMultiPolygon()
            for p in mp:
                n = len(p[0])
                part = []
                for i in range(n):
                    v = QgsPointXY(p[0][i])
                    part.append(v)
                self._geometry.append(part)
        else:
            polyG = g.asPolygon()
            n = len(polyG[0])
            part = []
            for i in range(n):
                v = QgsPointXY(polyG[0][i])
                part.append(v)
            self._geometry.append(part)

    def setMarkerIndex(self, m):
        self._markeridx = m

    def geometryTransform(self, xform):
        for part in self._geometry:
            for g in part:
                p = QgsPoint(g)
                p.transform(xform)
                g.setX(p.x())
                g.setY(p.y())

    def geometrypoints(self):
        polypoints = []
        for part in self._geometry:
            for g in part:
                p = QgsPointXY(g.toQPointF())
                polypoints.append(p)
        return polypoints

    def transform(self, canvas, paintxform=None):
        startpoint = None
        self.poly = []
        for part in self._geometry:
            polypoints = []
            for v in part:
                polypoints.append(canvas.toCanvasCoordinates(v).toPoint())
            self.poly.append(QPolygon(polypoints))
            if len(polypoints) > 0:
                self.polypoint = polypoints[0]

    def transformdraw(
        self, canvas, qp, paintxform, ptmarker, alpha, labelargs, label=None
    ):
        lastV = None
        startpoint = None

        self.poly = []
        for part in self._geometry:
            polypoints = []
            for v in part:
                polypoints.append(canvas.toCanvasCoordinates(v).toPoint())
            self.poly.append(QPolygon(polypoints))
            if len(polypoints) > 0:
                self.polypoint = polypoints[0]

        for poly in self.poly:
            qp.drawPolygon(poly)
        qp.drawPoint(
            self.polypoint
        )  # Draw a single point in case the polygon is too small to render
        if label and self._attr:
            self.drawlabel(qp, labelargs)

    def draw(self, canvas, qp, paintxform, ptmarker, alpha, labelargs, label=None):
        for poly in self.poly:
            qp.drawPolygon(poly)

        qp.drawPoint(
            self.polypoint
        )  # Draw a single point in case the polygon is too small to render

        if label and self._attr:
            self.drawlabel(qp, labelargs)

    def drawlabel(self, qp, labelargs):

        drawx = self.polypoint.x()
        drawy = self.polypoint.y()

        labelfont = qp.font()
        labelfont.setPointSize(labelargs.fontsize)
        labelfont.setWeight(QFont.ExtraBold)
        qp.setFont(labelfont)

        drawrect = QtCore.QRectF(
            drawx + labelargs.xoffset, drawy + labelargs.yoffset, 500, 500
        )
        qp.drawText(drawrect, self._attr)

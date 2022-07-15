#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

from qgis.core import *
from qgis.PyQt import QtCore, QtGui
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QFont
from .TimeDataElement import TimeDataElement


class TimeDataPoint(TimeDataElement):
    def __init__(
        self, geometry, fid, markeridx, epoch, duration=None, attr=None, size=None
    ):
        super().__init__(epoch, duration)
        pt = geometry.asPoint()
        self._point = QgsPointXY(pt.x(), pt.y())
        self._fid = fid
        self._markeridx = markeridx
        self._size = size
        self._attr = attr

    @property
    def fid(self):
        return self._fid

    @property
    def markeridx(self):
        return self._markeridx

    @property
    def size(self):
        return self._size

    @property
    def attr(self):
        return self._attr

    @property
    def point(self):
        return self._point

    def setMarkerIndex(self, m):
        self._markeridx = m

    def geometryTransform(self, xform):
        p = QgsPoint(self._point)
        p.transform(xform)
        self._point = QgsPointXY(p.x(), p.y())

    def geometrypoints(self):
        return [self._point]

    def asQPointF(self):
        qpt = QtCore.QPointF(self.x(), self.y())
        return qpt

    def transform(self, canvas, paintxform=None):
        self.drawpt = canvas.toCanvasCoordinates(self.point).toPoint()

    def draw(self, canvas, qp, paintxform, ptmarker, alpha, labelargs, uselabel):

        if paintxform:
            qp.setTransform(paintxform)
        if ptmarker:
            qp.drawImage(self.drawpt, ptmarker)
        else:
            qp.drawPoint(self.drawpt)
        if uselabel and self._attr:
            self.drawlabel(qp, labelargs)

    def transformdraw(
        self, canvas, qp, paintxform, ptmarker, alpha, labelargs, uselabel
    ):
        self.drawpt = canvas.toCanvasCoordinates(self.point)

        if paintxform:
            qp.setTransform(paintxform)
        if ptmarker:
            qp.drawImage(self.drawpt, ptmarker)
        else:
            qp.drawPoint(self.drawpt)
        if uselabel and self._attr:
            self.drawlabel(qp, labelargs)

    def drawlabel(self, qp, labelargs):

        drawx = self.drawpt.x()
        drawy = self.drawpt.y()

        labelfont = qp.font()
        labelfont.setPointSize(labelargs.fontsize)
        labelfont.setWeight(QFont.ExtraBold)
        qp.setFont(labelfont)

        drawrect = QtCore.QRectF(
            drawx + labelargs.xoffset, drawy + labelargs.yoffset, 500, 500
        )
        qp.drawText(drawrect, self._attr)

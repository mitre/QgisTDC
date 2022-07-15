#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

from qgis.PyQt import QtGui, QtCore
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *

from qgis.gui import QgsVertexMarker, QgsMapCanvasItem


class CanvasTextLayer(QgsMapCanvasItem):

    # This class will display text on the map in the upper left corner.
    # It is useful for displaying status or debugging info.

    def __init__(self, canvas):
        QgsMapCanvasItem.__init__(self, canvas)
        self.canvas = canvas

        self.textColor = QColor(200, 200, 0, 150)
        self.textSize = 8
        self.message = ""
        self.pen = QPen(self.textColor)
        self.pen.setWidth(3)
        self.rect = QRect(10, 10, 1000, 100)

    def setColor(self, c):
        self.textColor = c
        self.pen = QPen(self.textColor)
        self.pen.setWidth(3)

    def getColor(self):
        return self.textColor

    def setSize(self, s):
        self.textSize = s

    def getSize(self):
        return self.textSize

    def setPen(self, pen):
        self.pen = pen

    def clear(self):
        self.message = ""
        self.update()

    def setmessage(self, m):
        self.message = m
        self.update()

    def paint(self, qp, x, xx):
        qp.setPen(self.pen)
        qp.setFont(QFont("Decorative", self.textSize, QFont.ExtraBold))
        qp.drawText(self.rect, Qt.AlignLeft, self.message)

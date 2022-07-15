#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#
import sys, math, time
import numpy as np

from qgis.PyQt import QtGui, QtCore, QtWidgets
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import (
    QWidget,
    QPushButton,
    QCheckBox,
    QLabel,
    QMessageBox,
    QPushButton,
)
from qgis.core import (
    Qgis,
    QgsSingleSymbolRenderer,
    QgsCategorizedSymbolRenderer,
    QgsMessageLog,
)

from .QtdcExceptions import *


class HistoLineWidget(QWidget):
    # This is a custom widget providing a  flat timeline with a dragable time
    # window element.  It is useful for the overview timeline UI.
    def __init__(self, datalayer, timeline, parent=None):
        super(HistoLineWidget, self).__init__(parent)
        self.resize(self.size().width(), 3)
        self.datalayer = datalayer
        self.timeline = timeline
        self.histo = []
        self.gridlines = []
        self.gridmaxlabel = ""
        self.gridmidlabel = ""
        self.gridmid_y = 0
        self.color = datalayer.getColor()
        self.logscale = False
        self.datalayer.maplayer.rendererChanged.connect(self.rendererchanged)

        self.name = datalayer.maplayer.name()
        self.setStyleSheet("QCheckBox, QPushButton {background-color: rgba(0,0,0,30%)}")

        self.translatex = None

        self.destroyed.connect(self.timeline.histogramDestroyed)
        self.histmax = 0
        self.controlGeometries = []

    def getName(self):
        return self.name

    # Qt docs recommend implementing these in all sibling widgets even if unused.
    def mousePressEvent(self, mouseEvent):
        pass

    def mouseReleaseEvent(self, mouseEvent):
        pass

    def doubleclickEvent(self, mouseEvent):
        pass

    def mouseMoveEvent(self, mouseEvent):
        pass

    def editsettings(self):
        self.datalayer.editsettings()

    def zoomout(self):
        self.timeline.setrange(self.datalayer.getmintime(), self.datalayer.getmaxtime())
        self.timeline.resize()
        self.timeline.update()

    def setlayervisibility(self):
        self.visible = self.visibilityBox.isChecked()
        self.datalayer.setvisibility(self.visible)
        self.update()

    def closelayer(self):
        self.timeline.removetimeline(self)
        self.setParent(
            None
        )  # This should fire the destroyed signal causing timeline widget to update

    def setlogscale(self, log):
        self.logscale = log

    def getControlGeometries(self):
        return self.controlGeometries

    def rendererchanged(self):
        try:
            renderer = self.datalayer.maplayer.renderer()
            if isinstance(renderer, QgsSingleSymbolRenderer):
                self.datalayer.setSingleSymbol()
                layersymbol = renderer.symbol()
                self.color = layersymbol.color()
        except LayerMarkerException as e:
            # This is reported in HistogramWidget so just pass it here
            pass

    def _resize(self, tmin, tmax, hc):
        # when timeline is resized, re-generate the histogram of the timeline.  The
        # histogram bin count is the same as the horizontal pixel count of the widget.
        # Histogram bar height can be either linear or logarithmic.  The resulting
        # histogram structure will contain a collection of Qline objects (bars) to expedite
        # drawing.

        # Bail if the layer is still loading
        if self.datalayer.isLoading:
            QgsMessageLog.logMessage(
                "Histoline resize bailed during reload.", "QTDC", Qgis.Info
            )
            return

        size = self.size()
        w = size.width()
        QgsMessageLog.logMessage(
            "HistoLINE width: " + str(w) + " height: " + str(size.height()),
            "QTDC",
            Qgis.Info,
        )
        self.controlGeometries.clear()

        h = 1
        if tmax <= tmin:
            QgsMessageLog.logMessage(
                "Histo line BAILING (tmax less or equal to tmin). "
                + str(tmax)
                + " - "
                + str(tmin),
                "QTDC",
                Qgis.Info,
            )
            return

        tmin += self.datalayer.timeshift
        tmax += self.datalayer.timeshift

        bins = np.linspace(
            tmin, tmax, w - 4
        )  # The 4 pixel trim is to prevent the right/left borders from covering data

        self.histo = []
        self.gridlines = []

        y = []

        QgsMessageLog.logMessage(
            "HistoLINE time range: " + str(tmax) + " : " + str(tmin), "QTDC", Qgis.Info
        )

        if self.datalayer.isdurationlayer():
            data = self.datalayer.getdurationindex()
            for bin in bins:
                item = np.argwhere((bin <= data[:, 1]) & (data[:, 0] <= bin))
                # item = (np.nonzero((bin <= data[:,1]) & (data[:,0] <= bin)))
                y.append(item.shape[0])
            self.histmax = int(max(y))
            QgsMessageLog.logMessage(
                str(self.histmax) + " duration hist max", "QTDC", Qgis.Info
            )
            if self.histmax == 0:
                # Short data sets can fall 'between the bars' on extremely long timelines and not show.
                # If this data is in the timeline range, put it all on the nearest bar.
                startdata = data[0, 0]
                enddata = data[data.shape[0] - 1, 1]
                bardata = np.argwhere(
                    (enddata <= data[:, 1]) & (data[:, 0] >= startdata)
                )
                barindex = np.searchsorted(bins, startdata, side="left")
                if (barindex > 0) and (barindex < len(y)):
                    y[barindex] = bardata.shape[0]
                    self.histmax = bardata.shape[0]
                    QgsMessageLog.logMessage(
                        str(self.histmax) + " SHORT duration hist max",
                        "QTDC",
                        Qgis.Info,
                    )

        else:
            data = self.datalayer.gettimeindex()

            if len(data) > 0:
                QgsMessageLog.logMessage(
                    str(len(bins))
                    + " histoLINE bins across "
                    + str(tmax - tmin)
                    + " for "
                    + str(len(data)),
                    "QTDC",
                    Qgis.Info,
                )
                y, x = np.histogram(data, bins)
                self.histmax = int(max(y))
                if self.histmax > 0 and self.logscale:
                    self.histmax = math.log(self.histmax, 2)

        x = 3  # Offset first bar x position to avoid left border

        QgsMessageLog.logMessage("histo LINE bins: " + str(len(y)), "QTDC", Qgis.Info)
        QgsMessageLog.logMessage(
            "histo LINE max: " + str(self.histmax), "QTDC", Qgis.Info
        )

        for t in y:

            p1 = QPoint(x, 1)

            if t > 0:
                self.histo.append(p1)
            x = x + 1

        p1 = QPoint(0, int(self.size().height() / 2))
        p2 = QPoint(self.size().width(), int(self.size().height() / 2))
        gridline = QLine(p1, p2)
        self.gridlines.append(gridline)

        self.gridmaxlabel = str(self.histmax)
        self.gridmidlabel = str(int(self.histmax / 2))
        if self.logscale:
            self.gridmidlabel = ""

        self.gridmid_y = int(self.size().height() / 2)

    def pan(self, x):
        # Apply a horizontal translation to the histogram data, used to pan the histogram
        if x:
            self.translatex = x
        else:
            self.translatex = None

    def setHisto(self, h):
        self.histo = h

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)

        if self.translatex:
            qp.translate(self.translatex, 0)

        # #Draw the histogram bars
        barcolor = self.color

        barcolor.setAlpha(255)
        pen = QtGui.QPen(barcolor, 3, QtCore.Qt.SolidLine)
        qp.setPen(pen)
        for bar in self.histo:
            qp.drawPoint(bar)

        qp.end()

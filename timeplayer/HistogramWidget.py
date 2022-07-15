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


class HistogramWidget(QWidget):
    # This is a custom widget providing a timeline histogram with a dragable time
    # window element.
    def __init__(self, datalayer, timeline, parent=None):
        super(HistogramWidget, self).__init__(parent)
        self.setDatalayer(datalayer)
        self.timeline = timeline
        self.histo = []
        self.histoline = []
        self.gridlines = []
        self.gridmaxlabel = ""
        self.gridmidlabel = ""
        self.gridmid_y = 0
        self.gridmid_x = 0
        self.logscale = False

        # self.name = datalayer.maplayer.name()
        self.setStyleSheet(
            "QCheckBox, QPushButton {color: rgba(255,255,255,100%); background-color: rgba(0,0,0,40%)}"
        )

        # Initialize the control for closing the timeline and layer
        self.closeControl = QPushButton(self)
        self.closeControl.setToolTip("Remove this layer from timeline")
        self.closeControl.setIcon(QIcon(":/plugins/QgisTDC/icons/delete_16.png"))
        self.closeControl.clicked.connect(self.closelayer)

        # Initialize the control to select the timeline for drag and drop
        self.dragSelect = QPushButton(self)
        self.dragSelect.setToolTip("Select timeline to CHANGE ORDER or to SHIFT TIME ")
        self.dragSelect.setIcon(QIcon(":/plugins/QgisTDC/icons/draghand_16.png"))
        self.dragSelect.clicked.connect(self.dragselect)

        # Initialize the control for setting layer animation visibility
        self.visibilityBox = QCheckBox(self.name, self)
        self.visibilityBox.setMaximumHeight(20)
        self.visibilityBox.move(25, 15)
        self.visibilityBox.click()
        self.visible = self.visibilityBox.isChecked()
        self.visibilityBox.stateChanged.connect(self.setlayervisibility)

        # Initialize the map zoom control
        self.mapZoomControl = QPushButton(self)
        self.mapZoomControl.setToolTip("Zoom MAP to visible data in this layer")
        self.mapZoomControl.setIcon(QIcon(":/plugins/QgisTDC/icons/mapzoom_16.png"))
        self.mapZoomControl.clicked.connect(self.datalayer.getdisplayextent)

        # Initialize the zoom out control
        self.zoomOutControl = QPushButton(self)
        pmap = QPixmap("absoluteTime_16x16.png")
        self.zoomOutControl.setToolTip("Zoom TIMELINE to this layer")
        self.zoomOutControl.setIcon(QIcon(":/plugins/QgisTDC/icons/zoomout.png"))
        self.zoomOutControl.clicked.connect(self.zoomout)

        # Initialize the layer settings control
        self.settingsControl = QPushButton(self)
        self.settingsControl.setToolTip("Layer settings")
        self.settingsControl.setIcon(QIcon(":/plugins/QgisTDC/icons/settings_16.png"))
        self.settingsControl.clicked.connect(self.editsettings)

        # Initialize the layer reload control
        self.reloadControl = QPushButton(self)
        self.reloadControl.setToolTip("Reload the data for this layer")
        self.reloadControl.setIcon(QIcon(":/plugins/QgisTDC/icons/reload24.png"))
        self.reloadControl.clicked.connect(self.reloadlayer)

        # Initialize the control for canceling time shift
        self.shiftControl = QPushButton(self)
        self.shiftControl.setToolTip("Cancel time shift")
        self.shiftControl.setIcon(QIcon(":/plugins/QgisTDC/icons/delete_16.png"))
        self.shiftControl.clicked.connect(self.cancelShift)
        self.shiftControl.setVisible(False)

        self.shiftLabel = QLabel(self)
        self.shiftLabel.setStyleSheet("QLabel { color : red; }")
        font = QtGui.QFont("Serif", 10, QtGui.QFont.ExtraBold)
        self.shiftLabel.setFont(font)
        self.shiftLabel.setAttribute(Qt.WA_TranslucentBackground, True)
        self.shiftLabel.setVisible(False)
        self.shifted = False

        self.translatex = None

        self.destroyed.connect(self.timeline.histogramDestroyed)
        self.histmax = 0
        self.controlGeometries = []
        self.dragging = False

    def setDatalayer(self, dl):
        self.datalayer = dl
        self.color = self.datalayer.getColor()
        self.datalayer.maplayer.rendererChanged.connect(self.rendererchanged)
        self.name = self.datalayer.maplayer.name()
        self.datalayer.layerClose.connect(self.closelayer)

    def getName(self):
        return self.name

    def getLayer(self):
        return self.datalayer

    # Qt docs recommend implementing these in all sibling widgets even if unused.
    def mousePressEvent(self, mouseEvent):
        pass

    def mouseReleaseEvent(self, mouseEvent):
        pass

    def doubleclickEvent(self, mouseEvent):
        pass

    def mouseMoveEvent(self, mouseEvent):
        pass

    def dragselect(self):
        self.dragging = self.timeline.reOrder(self)
        QgsMessageLog.logMessage(
            "SELECT histogram dragging " + str(self.dragging), "QTDC", Qgis.Info
        )

    def dragdeselect(self):
        self.dragging = False
        QgsMessageLog.logMessage("DeSELECT histogram dragging", "QTDC", Qgis.Info)

    def editsettings(self):
        self.datalayer.editsettings()

    def reloadlayer(self):
        self.datalayer.requestReload()

    def cancelShift(self):
        self.datalayer.timeshift = 0
        self.shiftControl.setVisible(False)
        self.shiftLabel.setVisible(False)
        self.shifted = False
        self.timeline.refreshTimeplayer()
        self.timeline.resize()
        self.timeline.update()

    def setshiftString(self, text, sign):
        self.shiftString = sign + text
        self.shiftLabel.setText(self.shiftString)

    def shiftlayer(self, shiftTime):
        self.datalayer.timeshift = self.datalayer.timeshift + shiftTime
        timeString, sign = self.timeline.getDynamicTimeString(self.datalayer.timeshift)
        self.shiftString = sign + timeString
        self.shiftLabel.setText(self.shiftString)
        self.shiftControl.setVisible(True)
        self.shiftLabel.setVisible(True)
        self.shifted = True
        self.timeline.resize()
        self.timeline.update()

    def zoomout(self):
        self.timeline.setrange(self.datalayer.getmintime(), self.datalayer.getmaxtime())
        self.timeline.resize()
        self.timeline.timeplayer.step(0)
        self.timeline.update()

    def setlayervisibility(self):
        self.visible = self.visibilityBox.isChecked()
        self.datalayer.setvisibility(self.visible)
        self.draggable = self.visible
        self.update()

    def closelayer(self):
        self.datalayer.layerClose.disconnect(self.closelayer)
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
            mbox = QMessageBox()
            mbox.setIcon(QMessageBox.Information)
            mbox.setText(str(e))
            ret = mbox.exec_()

    def _resize(self, tmin, tmax, hc):
        # when timeline is resized, re-generate the histogram of the timeline.  The
        # histogram bin count is the same as the horizontal pixel count of the widget.
        # Histogram bar height can be either linear or logarithmic.  The resulting
        # histogram structure will contain a collection of Qline objects (bars) to expedite
        # drawing.
        size = self.size()
        w = size.width()
        h = size.height()
        QgsMessageLog.logMessage("Histogram width: " + str(w), "QTDC", Qgis.Info)

        # Reconstruct the control geometries used to mask mouse inputs to the timeline
        self.controlGeometries.clear()
        self.closeControl.setGeometry(w - 20, 0, 20, 20)
        self.dragSelect.setGeometry(2, 15, 20, 20)
        xoffset = self.dragSelect.width() + 5
        self.zoomOutControl.setGeometry(xoffset, 15, 20, 20)
        xoffset = xoffset + self.zoomOutControl.width() + 5
        self.mapZoomControl.setGeometry(xoffset, 15, 20, 20)
        xoffset = xoffset + self.mapZoomControl.width() + 5
        self.settingsControl.setGeometry(xoffset, 15, 20, 20)
        xoffset = xoffset + self.settingsControl.width() + 5
        self.reloadControl.setGeometry(xoffset, 15, 20, 20)
        xoffset = xoffset + self.reloadControl.width() + 10
        self.visibilityBox.setGeometry(
            xoffset, 15, self.visibilityBox.width(), self.visibilityBox.height()
        )
        xoffset = xoffset + self.visibilityBox.width() + 10
        self.shiftControl.setGeometry(xoffset, 15, 20, 20)
        xoffset = xoffset + self.shiftControl.width() + 5
        self.shiftLabel.setGeometry(
            xoffset, 10, self.shiftLabel.width() + 200, self.shiftLabel.height()
        )

        # Save the control geometries for use with the control mask of the histogram
        self.controlGeometries.append(self.closeControl.geometry())
        self.controlGeometries.append(self.dragSelect.geometry())
        self.controlGeometries.append(self.visibilityBox.geometry())
        self.controlGeometries.append(self.zoomOutControl.geometry())
        self.controlGeometries.append(self.mapZoomControl.geometry())
        self.controlGeometries.append(self.settingsControl.geometry())
        self.controlGeometries.append(self.reloadControl.geometry())
        if self.shifted:
            self.controlGeometries.append(self.shiftControl.geometry())
            QgsMessageLog.logMessage("Shift control geometry set", "QTDC", Qgis.Info)

        if hc > 0:
            h = int((size.height() - 15) / hc)
        else:
            h = 20
        h = size.height()
        if tmax == tmin:
            return

        tmin += self.datalayer.timeshift
        tmax += self.datalayer.timeshift

        bins = np.linspace(
            tmin, tmax, w - 4
        )  # The 4 pixel trim is to prevent the right/left borders from covering data

        self.histo = []
        self.histoline = []
        self.gridlines = []

        y = []

        QgsMessageLog.logMessage(
            "Histogram time range: " + str(tmax) + " : " + str(tmin), "QTDC", Qgis.Info
        )

        if self.datalayer.isdurationlayer():
            data = self.datalayer.getdurationindex()
            for bin in bins:
                item = np.argwhere((bin <= data[:, 1]) & (data[:, 0] <= bin))
                # item = (np.nonzero((bin <= data[:,1]) & (data[:,0] <= bin)))
                y.append(item.shape[0])
            self.histmax = int(max(y))
            if self.histmax > 0 and self.logscale:
                self.histmax = math.log(
                    self.histmax + 1, 2
                )  # add 1 to make small values more visible
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
                    if self.histmax > 0 and self.logscale:
                        self.histmax = math.log(
                            self.histmax + 1, 2
                        )  # add 1 to make small values more visible
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
                    + " histogram bins across "
                    + str(tmax - tmin)
                    + " for "
                    + str(len(data)),
                    "QTDC",
                    Qgis.Info,
                )
                y, x = np.histogram(data, bins)
                self.histmax = int(max(y))
                if self.histmax > 0 and self.logscale:
                    self.histmax = math.log(
                        self.histmax + 1, 2
                    )  # add 1 to make small values more visible

        x = 3  # Offset first bar x position to avoid left border

        QgsMessageLog.logMessage("histo bins: " + str(len(y)), "QTDC", Qgis.Info)
        QgsMessageLog.logMessage("histo max: " + str(self.histmax), "QTDC", Qgis.Info)

        for t in y:
            barheight = 0
            if self.histmax > 0:
                if self.logscale:
                    if t > 0:
                        barheight = math.log(
                            t + 1, 2
                        )  # add 1 to make small values more visible
                        barheight = (barheight / self.histmax) * h
                else:
                    barheight = int((t / self.histmax) * h)
            p1 = QPoint(x, h)
            p2 = QPoint(x, h - int(barheight))
            bar = QLine(p1, p2)
            self.histo.append(bar)
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
        self.gridmid_x = int(self.size().width() / 2)

    def pan(self, x):
        # Apply a horizontal translation to the histogram data to pan the histogram view
        if x:
            self.translatex = x
        else:
            self.translatex = None

    def paintEvent(self, e):

        qp = QtGui.QPainter()
        qp.begin(self)

        if self.translatex:
            qp.translate(self.translatex, 0)

        font = QtGui.QFont("Serif", 7, QtGui.QFont.Light)
        qp.setFont(font)

        # #Draw the histogram bars
        barcolor = self.color
        if (not self.visible) or self.datalayer.isLoading:
            barcolor.setAlpha(75)
        else:
            barcolor.setAlpha(255)
        pen = QtGui.QPen(barcolor, 2, QtCore.Qt.SolidLine)
        qp.setPen(pen)
        for bar in self.histo:
            qp.drawLine(bar)

        # Draw the grid lines
        gridcolor = QColor(120, 120, 120, 255)
        pen = QtGui.QPen(gridcolor, 1, QtCore.Qt.DotLine)
        qp.setPen(pen)
        for gridline in self.gridlines:
            qp.drawLine(gridline)

        # Draw the bar height labels on the left side of the histogram
        qp.drawText(5, 10, self.gridmaxlabel)
        qp.drawText(5, self.gridmid_y + 10, self.gridmidlabel)

        if self.dragging:
            pen = QtGui.QPen(QColor(0, 200, 200), 3, QtCore.Qt.SolidLine)
            qp.setPen(pen)
            qp.drawRect(1, 1, self.size().width() - 2, self.size().height() - 2)

        # Draw the loading label (only happens when data reload in progress)
        if self.datalayer.isLoading:
            font.setPixelSize(24)
            fm = qp.fontMetrics()
            loadText = self.datalayer.loadBanner
            pixelsWide = int(fm.width(loadText) / 2)
            pixelsHigh = int(fm.height() / 2)
            qp.setFont(font)
            redpen = QPen(QColor(255, 50, 100, 255))
            qp.setPen(redpen)
            qp.drawText(
                self.gridmid_x - pixelsWide, self.gridmid_y + pixelsHigh, loadText
            )

        qp.end()

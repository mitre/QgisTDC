#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import sys, math, time
import numpy as np
import pytz
from datetime import datetime

from qgis.PyQt import QtGui, QtCore, QtWidgets
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSizePolicy
from qgis.core import Qgis, QgsMessageLog, QgsApplication

from .HistoLineWidget import HistoLineWidget
from .TimelineBarWidget import TimelineBarWidget
from .TimelineZoomWidget import TimelineZoomWidget


class TimelineOverviewWidget(QWidget):
    # This is a custom widget providing a container for multiple timeline histograms with a draggable time
    # window element.

    i32min = -2147483648
    i32max = 2147483647

    def __init__(self, player, parent=None):
        super(TimelineOverviewWidget, self).__init__(parent)
        self.timeplayer = player
        self.initUI()

    def initUI(self):

        # self.setMinimumSize(1, 25)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.dragging = False
        # Set mousetracking to false so mousemoveevents only come when dragging
        self.setMouseTracking(False)
        self.time = 0
        self.stepsize = 0
        self.history = 0
        self.tmin = 0
        self.tmax = 0
        self.viewTimeRange = 0
        self.histos = []
        self.logscale = False
        self.timestring = ""
        self.historystring = ""
        self.tminmark = None
        self.startstring = ""
        self.endstring = ""
        self.barEnd = None
        self.barStart = None
        self.timeExtent = 0
        self.timeExtentmin = 0

        self.starttime = None
        self.endtime = None

        self.pencolor = QtGui.QColor(20, 20, 20)

        self.hbox = QHBoxLayout()

        # Add the barwidget that draws the start/end time bars over the histograms
        # We need to manage its size and show() it because it is not in a layout

        zoomEndLineColor = QtGui.QColor(100, 200, 255)
        self.zoomwidget = TimelineZoomWidget(self, zoomEndLineColor)
        self.zoomwidget.resize(self.size().width(), self.size().height())
        self.zoomwidget.show()

        self.barwidget = TimelineBarWidget(self, False)
        self.barwidget.resize(self.size().width(), self.size().height())
        self.barwidget.show()

        self.tlvbox = QVBoxLayout()

        self.vbox = QVBoxLayout()
        self.vbox.setSpacing(0)
        self.vbox.setContentsMargins(0, 16, 0, 0)
        self.vbox.addLayout(self.tlvbox)
        self.setLayout(self.vbox)

        self.zoomjournal = []
        QgsMessageLog.logMessage("OVERVIEW TIMELINE INITIALIZED.", "QTDC", Qgis.Info)

    def setTimeline(self, tl):
        self.timeline = tl

    def setextent(self, tmin, tmax):
        QgsMessageLog.logMessage(
            "OVERVIEW TIMELINE set EXTENT: " + str(tmin) + ", " + str(tmax),
            "QTDC",
            Qgis.Info,
        )
        self.timeExtentmin = tmin
        self.timeExtentmax = tmax
        self.timeExtent = tmax - tmin
        self.barwidget.setrange(tmin, tmax)
        self.resize()

        # time label for timeline start
        try:
            starttime = datetime.fromtimestamp(self.timeExtentmin).astimezone(pytz.utc)
            self.startstring = starttime.strftime("%Y-%m-%d")
        except Exception as ex1:
            self.startstring = "NaN"
        # time label for timeline end
        try:
            endtime = datetime.fromtimestamp(self.timeExtentmax).astimezone(pytz.utc)
            self.endstring = endtime.strftime("%Y-%m-%d")
        except Exception as ex2:
            self.endstring = "NaN"

    def refreshrange(self):
        QgsMessageLog.logMessage("OVERVIEW TIMELINE refresh range", "QTDC", Qgis.Info)
        if self.starttime and self.endtime:
            self.setrange(self.starttime, self.endtime)

    def setStep(self, s):
        self.stepsize = s

    def logcheck(self, l):
        self.logscale = l
        self.resize()
        self.update()

    def wheelEvent(self, QWheelEvent):
        degrees = QWheelEvent.angleDelta() / 8
        if degrees:
            steps = degrees.y() / 15
            pos = self.zoomwidget.getCenterX()
            size = self.size()
            w = size.width()
            stepamount = max(
                1, self.stepsize
            )  # to prevent operator confusion if stepsize=0, only used with TL zoom

            newtime = (
                (((pos) / (w)) * self.viewTimeRange)
                + self.timeExtentmin
                + (steps * self.stepsize)
            )
            newmin = self.tmin + (steps * stepamount)
            newmax = self.tmax - (steps * stepamount)
            self.update()

            hist = self.zoomwidget.getHistory()

            deltat = -((steps * stepamount * 10) / w) * self.timeExtent

            position = self.zoomwidget.getPosition() + (steps * stepamount * 10)

            newtime = ((position / w) * self.viewTimeRange) + self.timeExtentmin
            newhistory = ((hist / w) * self.viewTimeRange) + self.timeExtentmin

            self.timeline.shift(deltat)
            self.timeplayer.step(0)

    def mousePressEvent(self, mouseEvent):
        pos = mouseEvent.pos()
        size = self.size()
        w = size.width()

        self.startpos = pos.x()

        self.dragStarttime = (
            ((self.startpos) / (w)) * self.timeExtent
        ) + self.timeExtentmin
        if mouseEvent.button() == Qt.RightButton:
            timeposition = self.zoomwidget.getPosition()
            histposition = self.zoomwidget.getHistory()
            if abs(pos.x() - timeposition) < abs(pos.x() - histposition):
                self.barEnd = timeposition
            else:
                self.barStart = histposition

    def mouseMoveEvent(self, mouseEvent):
        # #When the mouse is dragged, update the timewindow position,
        # #pause the timeplayer animation, and display data for timewindow
        pos = mouseEvent.pos()

        size = self.size()
        w = size.width()
        deltax = pos.x() - self.startpos
        self.startpos = pos.x()
        if mouseEvent.buttons() == Qt.RightButton:
            if self.barStart:
                self.zoomwidget.stretchBack(pos)
                self.zoomtimestart = (
                    ((pos.x()) / (w)) * self.timeExtent
                ) + self.timeExtentmin
            elif self.barEnd:
                self.zoomwidget.stretch(pos)
                self.zoomtimeend = (
                    ((pos.x()) / (w)) * self.timeExtent
                ) + self.timeExtentmin
        else:
            self.zoomwidget.move(deltax)

        self.update()

    def mouseReleaseEvent(self, mouseEvent):
        # #Update timewindow position at release of mouse (click or drag)
        # #and set the timeplayer play position to resume animation at the
        # #new time position.

        size = self.size()
        w = size.width()
        pos = mouseEvent.pos()

        timeposition = self.zoomwidget.getPosition()
        histposition = self.zoomwidget.getHistory()

        starttime = (((histposition) / (w)) * self.timeExtent) + self.timeExtentmin
        endtime = (((timeposition) / (w)) * self.timeExtent) + self.timeExtentmin
        self.timeline.setrange(starttime, endtime)
        self.timeline.resize()
        self.timeline.update()

        self.timeplayer.step(0)
        self.barEnd = None
        self.barStart = None

    def pan(self, x=None):
        # Shift the x position of the histogram data during panning
        for h in self.histos:
            h.pan(x)

    def histocount(self):
        return len(self.histos)

    def settime(self, t, h):
        self.barwidget.settime(t, h)
        self.update()

    def clearjournal(self):
        self.zoomjournal = []

    def zoomback(self):
        jLength = len(self.zoomjournal)
        QgsMessageLog.logMessage(
            "TIMELINEOVERVIEWWIDGET:  Zoomback: " + str(len(self.zoomjournal)),
            "QTDC",
            Qgis.Info,
        )
        if jLength > 1:
            # The current zoom level is in the journal so first remove it to get the previous
            zoomrange = self.zoomjournal.pop(0)
            zoomrange = self.zoomjournal.pop(0)
            self.setrange(zoomrange[0], zoomrange[1])

    def setrange(self, start, end, journal=True):
        """

        Set the time range of the view window element of the overview timeline.
        Params:
            start: start time
            end:   end time
            journal:  use journaling

        """

        QgsMessageLog.logMessage("OVERVIEW TIMELINE setting range", "QTDC", Qgis.Info)
        if self.timeExtent > 0:
            self.starttime = start
            self.endtime = end
            self.viewTimeRange = end - start

            self.startx = int(
                self.size().width() * ((start - self.timeExtentmin) / self.timeExtent)
            )
            self.endx = int(
                self.size().width() * ((end - self.timeExtentmin) / self.timeExtent)
            )

            # Clip the start and end values to within the display area
            w = self.size().width()
            self.startx = w if self.startx > w else self.startx
            self.startx = 0 if self.startx < 0 else self.startx
            self.endx = w if self.endx > w else self.endx
            self.endx = 0 if self.endx < 0 else self.endx

            self.rangex = self.endx - self.startx
            self.zoomwidget.place(QPoint(self.startx, 0))
            self.zoomwidget.stretch(QPoint(self.endx, 0))
            self.zoomwidget.update()

    def reset(self):
        # Clear the histogram and timewindow position info
        self.barwidget.reset()
        self.histos = []
        for i in reversed(range(self.tlvbox.count())):
            item = self.tlvbox.itemAt(i).widget()
            item.setParent(None)

    def addtimeline(self, tdl, histogram):
        newhisto = HistoLineWidget(tdl, self)
        self.histos.append(newhisto)
        self.tlvbox.insertWidget(0, newhisto)
        newhisto.stackUnder(self.barwidget)
        newhisto.stackUnder(self.zoomwidget)
        self.flushUIevents()
        histogram.destroyed.connect(lambda: self.removetimeline(newhisto))

    def movetimeline(self, fromidx, toidx):
        if (toidx >= 0) and (toidx <= self.tlvbox.count() - 1):
            histoline = self.tlvbox.itemAt(fromidx).widget()
            self.tlvbox.removeWidget(histoline)
            self.tlvbox.insertWidget(toidx, histoline)

    def removetimeline(self, histogram):
        self.histos.remove(histogram)
        histogram.setParent(None)
        QgsMessageLog.logMessage(
            "OVERVIEW TIMELINE...remove timeline. " + histogram.getName(),
            "QTDC",
            Qgis.Info,
        )

    def histogramDestroyed(self):
        QgsMessageLog.logMessage(
            "OVERVIEW TIMELINE...timeline removed. "
            + str(len(self.histos))
            + " remain.",
            "QTDC",
            Qgis.Info,
        )
        # Flush UI events so that remaining histograms are properly rendered
        self.flushUIevents()
        self.resize()
        self.update()

    def flushUIevents(self):
        QgsApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

    def resize(self):

        # when timeline is resized, also resize the histograms.

        self.barwidget.resize(self.size().width(), self.size().height())
        self.zoomwidget.resize(self.size().width(), self.size().height())

        region = QRegion(self.rect())
        histoct = len(self.histos)
        # Resize the individual histograms and apply a mask to the barwidget for their control geometries
        for h in self.histos:
            h._resize(self.timeExtentmin, self.timeExtentmax, histoct)
            self.pencolor = QtGui.QColor(100, 100, 100)
            hpos = h.pos()
            hcontrolgeo = h.getControlGeometries()
            for geo in hcontrolgeo:
                geo.moveTo(geo.x(), hpos.y() + geo.y())
                region -= QRegion(geo)
        self.barwidget.setMask(region)

    def paintEvent(self, e):

        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawWidget(qp)
        qp.end()

    def drawWidget(self, qp):
        # Main drawing method for widget.
        #
        font = QtGui.QFont("Serif", 7, QtGui.QFont.Light)
        qp.setFont(font)

        size = self.size()
        w = size.width()
        h = size.height()  # Trim 15 pixels from the bottom for timeline labels

        step = int(round(w / 10.0))  # Get step size across x axis for timeline labels

        pen = QtGui.QPen(self.pencolor, 1, QtCore.Qt.SolidLine)

        qp.setPen(pen)
        qp.setBrush(QtCore.Qt.NoBrush)
        qp.drawRect(0, 16, w - 1, h - 1)

        metrics = qp.fontMetrics()
        fh = metrics.height()

        starttick = self.timeExtentmin
        # #tick marks and timeline labels for x axis
        for i in range(step, 10 * step, step):

            qp.drawLine(i, 9, i, 15)
            ticktime = (i / w) * self.timeExtent + self.timeExtentmin
            try:
                tickdeltatime = ticktime - starttick
                starttick = ticktime
                tickdatetime = datetime.fromtimestamp(ticktime).astimezone(pytz.utc)
                if tickdeltatime > 4752000:  # 55 days or more per tick (as seconds)
                    tickstring = tickdatetime.strftime("%b %Y")
                elif tickdeltatime > 10800:  # 3 hours or more per tick (as seconds)
                    tickstring = tickdatetime.strftime("%b-%d %H:%M")
                else:
                    tickstring = tickdatetime.strftime("%H:%M:%S.%f")[:-4]

            except Exception as e:
                tickstring = "NaN"
            fw = metrics.width(tickstring)
            qp.drawText(int(i - fw / 2), fh, tickstring)

        qp.drawText(2, fh, self.startstring)

        # metrics = qp.fontMetrics()
        fw = metrics.width(self.endstring)
        qp.drawText(w - fw, fh, self.endstring)

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
from qgis.PyQt.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton
from qgis.core import Qgis, QgsMessageLog, QgsApplication

from .HistogramWidget import HistogramWidget
from .TimelineBarWidget import TimelineBarWidget
from .TimelineZoomWidget import TimelineZoomWidget


class TimelineWidget(QWidget):
    # This is a custom widget providing a container for multiple timeline histograms with a draggable time
    # window element.

    def __init__(self, player, overview, parent=None):
        super(TimelineWidget, self).__init__(parent)
        self.timeplayer = player
        self.messageBar = player.getMessageBar()
        self.overview = overview
        self.overview.setTimeline(self)
        self.initUI()

    def initUI(self):

        self.setMinimumSize(1, 30)
        self.dragging = False
        # Set mousetracking to false so mousemoveevents only come when dragging
        self.setMouseTracking(False)
        self.time = 0
        self.stepsize = 0
        self.history = 0
        self.min = 0
        self.max = 0
        self.range = 0
        self.histos = []
        self.logscale = False
        self.timestring = ""
        self.historystring = ""
        self.minmark = None
        self.startstring = ""
        self.endstring = ""
        self.barEnd = None
        self.barStart = None

        self.pencolor = QtGui.QColor(20, 20, 20)

        # Create and set up the buttons for specifying the visible limit of the timeline manually.
        # CURRENTLY DISABLED. UNCOMMENT THIS BLOCK TO ENABLE.
        # self.startLimit = QPushButton(self)
        # self.startLimit.setToolTip("Set timeline visible limit")
        # self.startLimit.setIcon(QIcon(":/plugins/QgisTDC/icons/Clock24.png"))
        # self.startLimit.setGeometry(0, self.height()-15, 20, 20)
        # self.startLimit.clicked.connect(self.setStartLimit)
        # self.endLimit = QPushButton(self)
        # self.endLimit.setToolTip("Set timeline visible limit")
        # self.endLimit.setIcon(QIcon(":/plugins/QgisTDC/icons/Clock24.png"))
        # self.endLimit.setGeometry(0, self.height()-15, 20, 20)
        # self.endLimit.clicked.connect(self.setEndLimit)
        # self.timeLimitDialog = TimeValueDialog()
        # self.startLocked = False
        # self.endLocked = False

        self.hbox = QHBoxLayout()

        # Add the barwidget that draws the start/end time bars over the histograms
        # We need to manage its size and show() it because it is not in a layout
        self.barwidget = TimelineBarWidget(self)
        self.barwidget.resize(
            self.size().width(), self.size().height() - 16
        )  # 16 pixels raises it above the time labels
        self.barwidget.show()

        self.zoomwidget = TimelineZoomWidget(self)
        self.zoomwidget.resize(self.size().width(), self.size().height() - 16)
        self.zoomwidget.show()

        self.tlvbox = QVBoxLayout()

        self.vbox = QVBoxLayout()
        self.vbox.setSpacing(2)
        self.vbox.setContentsMargins(
            0, 0, 0, 15
        )  # put a 15 pixel margin at the bottom of the layout for the time labels
        self.vbox.addLayout(self.tlvbox)
        self.setLayout(self.vbox)

        self.zoomjournal = []
        # self.windowlocked = False

        self.box = QRect(0, 0, 0, 0)
        self.timelineReOrder = False
        self.draghisto = []
        self.timeshiftamount = 0

    # def setStartLimit(self):
    # #Initialize the time limit dialog with the start time parameters
    # self.timeLimitDialog.lockBox.setChecked(self.startLocked)
    # dt = QDateTime()
    # dt.setSecsSinceEpoch(self.min)
    # self.timeLimitDialog.dateTimeEdit.setTimeSpec(Qt.UTC)  #Display time as UTC
    # self.timeLimitDialog.dateTimeEdit.setDateTime(dt.toUTC())
    # self.timeLimitDialog.show()

    # # Run the dialog event loop
    # result = self.timeLimitDialog.exec_()
    # # See if OK was pressed
    # if result:
    # #Apply the dialog selections to the timeline: start time, lock status
    # dt = self.timeLimitDialog.dateTimeEdit.dateTime()
    # newmin = dt.toSecsSinceEpoch()
    # self.startLocked = False
    # self.setrange(newmin, self.max, False)
    # self.resize()
    # self.update()
    # self.startLocked = self.timeLimitDialog.lockBox.isChecked()
    # if self.startLocked:  #Set the button icon according to lock status
    # self.startLimit.setIcon(QIcon(":/plugins/QgisTDC/icons/redLock24.png"))
    # self.messageBar.pushMessage("The LOWER timline view limit is locked.  Timline PAN/ZOOM operations will be restricted by this limit.", level=Qgis.Info, duration=7)
    # else:
    # self.startLimit.setIcon(QIcon(":/plugins/QgisTDC/icons/Clock24.png"))

    # def setEndLimit(self):
    # #Initialize the time limit dialog with the end time parameters
    # self.timeLimitDialog.lockBox.setChecked(self.endLocked)
    # dt = QDateTime()
    # dt.setSecsSinceEpoch(self.max)
    # self.timeLimitDialog.dateTimeEdit.setTimeSpec(Qt.UTC)  #Display time as UTC
    # self.timeLimitDialog.dateTimeEdit.setDateTime(dt.toUTC())
    # self.timeLimitDialog.show()
    # # Run the dialog event loop
    # result = self.timeLimitDialog.exec_()
    # # See if OK was pressed
    # if result:
    # dt = self.timeLimitDialog.dateTimeEdit.dateTime()
    # newmax = dt.toSecsSinceEpoch()
    # self.endLocked = False
    # self.setrange(self.min, newmax, False)
    # self.resize()
    # self.update()
    # self.endLocked = self.timeLimitDialog.lockBox.isChecked()
    # if self.endLocked:  #Set the button icon according to lock status
    # self.endLimit.setIcon(QIcon(":/plugins/QgisTDC/icons/redLock24.png"))
    # self.messageBar.pushMessage("The UPPER timline view limit is locked.  Timline PAN/ZOOM operations will be restricted by this limit.", level=Qgis.Info, duration=7)
    # else:
    # self.endLimit.setIcon(QIcon(":/plugins/QgisTDC/icons/Clock24.png"))

    # def lockwindow(self, l):
    # self.windowlocked = l

    def setStep(self, s):
        self.stepsize = s

    def logcheck(self, l):
        self.logscale = l
        self.resize()
        self.update()

    def getDurationString(self):
        return self.barwidget.getDurationString()

    def wheelEvent(self, QWheelEvent):
        degrees = QWheelEvent.angleDelta() / 8
        if degrees:
            steps = degrees.y() / 15
            pos = self.barwidget.getPosition()
            size = self.size()
            w = size.width()
            stepamount = max(
                1, self.stepsize
            )  # to prevent operator confusion if stepsize=0

            sign = -1 if steps < 0 else 1

            modifier = QWheelEvent.modifiers()
            if not self.timelineReOrder:
                if modifier == Qt.ControlModifier:
                    newmin = self.min + (steps * stepamount)
                    newmax = self.max - (steps * stepamount)
                    if (
                        newmax - newmin
                    ) > 0:  # prevent problems in case newmin and newmax cross each other
                        self.setrange(newmin, newmax, False)
                    self.resize()
                    self.timeplayer.step(
                        0
                    )  # Places the time window at the current time
                    self.update()

                elif modifier == Qt.ShiftModifier:
                    newmin = self.min + (steps * stepamount)
                    newmax = self.max + (steps * stepamount)
                    if (
                        newmax - newmin
                    ) > 0:  # prevent problems in case newmin and newmax cross each other
                        self.setrange(newmin, newmax, False)
                    self.resize()
                    self.timeplayer.step(
                        0
                    )  # Places the time window at the current time
                    self.update()

                else:
                    self.timeplayer.setpause(True)
                    self.timeplayer.step(stepamount * sign)
                    self.update()
            else:  # Timeline is in re-ordering mode
                if len(self.draghisto) == 1:
                    self.moveHistogram(self.draghisto[0], steps)

    def mousePressEvent(self, mouseEvent):

        if not self.timelineReOrder:
            pos = mouseEvent.pos()
            size = self.size()
            w = size.width()
            newtime = (((pos.x()) / (w)) * self.range) + self.min

            self.startpos = pos

            modifier = mouseEvent.modifiers()
            if (
                mouseEvent.button() == Qt.RightButton
            ):  # Right mouse is used to adjust time window (barwidget)
                if modifier != Qt.ControlModifier:
                    self.barwidget.showDuration(True)
                    self.timeplayer.setpause(True)
                    self.history = self.timeplayer.gethistory()
                    timepos = self.barwidget.getPosition()
                    histpos = self.barwidget.getHistPosition()
                    if abs(pos.x() - timepos) < abs(pos.x() - histpos):
                        self.barStart = timepos
                    else:
                        self.barEnd = histpos
            else:
                if (modifier == Qt.ControlModifier) or (modifier == Qt.ShiftModifier):
                    if not self.minmark:
                        self.minmark = newtime
                        self.zoomwidget.place(pos)
                        self.zoomwidget.setVisible(True)
                else:
                    self.timeplayer.setpause(True)
                    self.barwidget.movebar(pos)
        else:
            if mouseEvent.button() == Qt.RightButton:
                pos = mouseEvent.pos()
                size = self.size()
                w = size.width()
                self.shiftstarttime = (((pos.x()) / (w)) * self.range) + self.min
                self.shiftstartx = pos.x()
                self.timeshiftamount = 0

    def mouseMoveEvent(self, mouseEvent):

        if not self.timelineReOrder:
            # When the mouse is dragged, update the timewindow position,
            # pause the timeplayer animation, and display data for timewindow

            pos = mouseEvent.pos()

            # self.barwidget.movebar(pos)
            size = self.size()
            w = size.width()
            newtime = (((pos.x()) / (w)) * self.range) + self.min

            modifier = mouseEvent.modifiers()
            if mouseEvent.buttons() == Qt.RightButton:
                if modifier != Qt.ControlModifier:
                    if self.barStart:  # Adjust the start of the time window
                        oldtime = (((self.barStart) / (w)) * self.range) + self.min
                        dt = newtime - oldtime
                        if (self.history + dt) > 0.01:
                            self.timeplayer.adjusthistory(self.history + dt)
                        self.timeplayer.showdata(newtime)
                    elif self.barEnd:
                        oldtime = (((self.barEnd) / (w)) * self.range) + self.min
                        bartime = (
                            ((self.barwidget.getPosition()) / (w)) * self.range
                        ) + self.min
                        dt = newtime - oldtime
                        if (self.history - dt) > 0.01:
                            self.timeplayer.adjusthistory(self.history - dt)
                            self.timeplayer.showdata(bartime)
                        else:
                            self.timeplayer.showdata(newtime)
                    self.update()
            else:
                modifier = mouseEvent.modifiers()

                if modifier == Qt.ControlModifier:
                    # Zoom the timeline
                    self.setCursor(Qt.SizeHorCursor)
                    self.zoomwidget.stretch(
                        pos, True
                    )  # allow zoom widget drag crossover
                    self.update()
                elif modifier == Qt.ShiftModifier:
                    # Pan the timeline
                    self.setCursor(Qt.SplitHCursor)
                    self.zoomwidget.place(pos)
                    dx = pos.x() - self.startpos.x()
                    self.pan(dx)
                    self.update()
                else:
                    # self.timeplayer.setpause(True)
                    self.barwidget.movebar(pos)
                    self.timeplayer.showdata(newtime)
                    self.update()
        else:
            if mouseEvent.buttons() == Qt.RightButton:
                pos = mouseEvent.pos()
                size = self.size()
                w = size.width()
                newtime = (((pos.x()) / (w)) * self.range) + self.min
                self.timeshiftamount = self.shiftstarttime - newtime
                timestring, sign = self.getDynamicTimeString(
                    self.draghisto[0].datalayer.timeshift + self.timeshiftamount
                )
                self.draghisto[0].setshiftString(timestring, sign)
                self.draghisto[0].pan(pos.x() - self.shiftstartx)
                self.update()

    def mouseReleaseEvent(self, mouseEvent):

        if self.timelineReOrder:
            if mouseEvent.button() == Qt.RightButton:
                self.draghisto[0].shiftlayer(self.timeshiftamount)
                self.draghisto[0].translatex = None
                # Call timeplayer to establish data limits
                self.refreshTimeplayer()
                self.resize()
                # Need to reset clip window if set because shifting corrupts clip settings.
                self.resumeplaywindow()
                QgsMessageLog.logMessage(
                    "TIME SHIFT AMOUNT: " + str(self.timeshiftamount), "QTDC", Qgis.Info
                )
            else:
                self.timelineReOrder = False
                self.draghisto[0].dragdeselect()
                self.draghisto = []
                self.resize()
        else:
            # Update timewindow position at release of mouse (click or drag)
            # and set the timeplayer play position to resume animation at the
            # new time position.
            pos = mouseEvent.pos()
            size = self.size()
            w = size.width()
            newtime = (((pos.x()) / w) * self.range) + self.min
            self.barEnd = None
            self.barStart = None
            self.setCursor(Qt.ArrowCursor)

            modifier = mouseEvent.modifiers()
            if mouseEvent.button() == Qt.RightButton:
                self.barwidget.showDuration(False)
                if modifier == Qt.ControlModifier:
                    self.zoomback()
                    self.resize()
            else:
                modifier = mouseEvent.modifiers()

                if modifier == Qt.ControlModifier:
                    if self.minmark:
                        delta = newtime - self.minmark
                        if delta > 0:  # zoom in
                            self.setrange(self.minmark, newtime)
                        elif delta < 0:  # zoom out (delta must not be zero)
                            zoomfactor = ((self.range / delta) * self.range) / 2
                            zoomfactor = abs(zoomfactor)
                            newmin = self.min - zoomfactor
                            newmax = self.max + zoomfactor
                            self.setrange(newmin, newmax)

                        self.resize()

                elif modifier == Qt.ShiftModifier:
                    if self.minmark:
                        delta = newtime - self.minmark
                        newmax = self.max - delta
                        newmin = newmax - self.range
                        self.setrange(newmin, newmax)

                        self.resize()
                else:
                    self.barwidget.movebar(pos)
                    self.timeplayer.setplayposition(newtime)
                    self.timeplayer.showdata(newtime)

            self.zoomwidget.reset()
            self.zoomwidget.setVisible(False)
            self.minmark = None
            self.pan()  # clear histogram horizontal shift (from panning)

        self.timeplayer.step(0)  # Places the time window at the current time
        self.update()
        QgsMessageLog.logMessage(
            "TimelineRelease: " + str(self.timelineReOrder), "QTDC", Qgis.Info
        )

    def getDynamicTimeString(self, t):
        # Create a time string that uses units appropriate to the amount of time represented
        timeinput = abs(t)
        days = 0
        hours = 0
        minutes = 0
        seconds = 0
        if timeinput >= 86400:
            days = int(timeinput / 86400)
            hours = int((timeinput % 86400) / 3600)
            minutes = int((timeinput % 3600) / 60)
            seconds = (timeinput % 3600) % 60
            timestring = (
                str(days)
                + "d "
                + "{:02d}".format(hours)
                + "h "
                + "{:02d}".format(minutes)
                + "m "
                + "%05.2f" % seconds
                + "s"
            )
        elif timeinput >= 3600:
            hours = int(timeinput / 3600)
            minutes = int((timeinput % 3600) / 60)
            seconds = (timeinput % 3600) % 60
            timestring = (
                "{:02d}".format(hours)
                + "h "
                + "{:02d}".format(minutes)
                + "m "
                + "%05.2f" % seconds
                + "s"
            )
        elif timeinput >= 60:
            minutes = int((timeinput % 3600) / 60)
            seconds = (timeinput % 3600) % 60
            timestring = "{:02d}".format(minutes) + "m " + "%05.2f" % seconds + "s"
        else:
            seconds = timeinput
            timestring = "%05.2f" % seconds + " seconds"

        sign = "+"
        if t < 0:
            sign = "-"
        return timestring, sign

    def refreshTimeplayer(self):
        self.timeplayer.setDataLimits()

    def setMove(self):
        self.move = True

    def shift(self, delta):
        newmax = self.max - delta
        newmin = newmax - self.range
        self.setrange(newmin, newmax)

        self.resize()
        self.update()

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
            "Zoomback: " + str(len(self.zoomjournal)), "QTDC", Qgis.Info
        )
        if jLength > 1:
            # The current zoom level is in the journal so first remove it to get the previous
            zoomrange = self.zoomjournal.pop(0)
            zoomrange = self.zoomjournal.pop(0)
            self.setrange(zoomrange[0], zoomrange[1])

    def resumeplaywindow(self):
        self.timeplayer.setplaywindow(self.min, self.max)

    def setrange(self, start, end, journal=True):

        # Check the lock status UNCOMMENT WITH BUTTON CODE IN INIT
        # if self.startLocked:
        # start = self.min
        # if self.endLocked:
        # end = self.max

        if start > end:
            QgsMessageLog.logMessage("Bad timeline range values.", "QTDC", Qgis.Info)
            self.messageBar.pushMessage(
                "Timline view could not be adjusted with specified limits.  Lower limit must be less than upper limit.  Timeline view limit lock may be interfering.",
                level=Qgis.Warning,
                duration=7,
            )

            return

        if journal:
            self.zoomjournal.insert(0, [start, end])

        # If start == end, pad the range to ensure non-zero range
        if start == end:
            self.setrange(start - 1, end + 1)
            return

        self.timeplayer.setplaywindow(start, end)

        self.overview.setrange(start, end)
        # Set the time range of the timeline
        self.min = start
        self.max = end
        self.range = end - start
        self.barwidget.setrange(start, end)

        # time label for timeline start
        try:
            starttime = datetime.fromtimestamp(self.min).astimezone(pytz.utc)
            # self.startstring = starttime.strftime('%Y-%m-%d %H:%M:%S.%f')[:-4] #slice off last 4 digits to get 2 decimal places
            self.startstring = starttime.strftime("%Y-%m-%d")
        except Exception as ex1:
            self.startstring = "NaN"
        # time label for timeline end
        try:
            endtime = datetime.fromtimestamp(self.max).astimezone(pytz.utc)
            # self.endstring = endtime.strftime('%Y-%m-%d %H:%M:%S.%f')[:-4] #slice off last 4 digits to get 2 decimal places
            self.endstring = endtime.strftime("%Y-%m-%d")
        except Exception as ex2:
            self.endstring = "NaN"

    def reset(self):
        # Clear the histogram and timewindow position info
        self.barwidget.reset()
        self.histos = []
        for i in reversed(range(self.tlvbox.count())):
            item = self.tlvbox.itemAt(i).widget()
            item.setParent(None)

    def reOrder(self, histo):
        if len(self.draghisto) == 0:
            self.timeplayer.setpause(True)
            self.draghisto.append(histo)
            self.timelineReOrder = True
            self.messageBar.pushMessage(
                "Timeline manipulation ACTIVATED.  Scroll MOUSE WHEEL to change TIMELINE ORDER.   Drag RIGHT MOUSE for TIME SHIFT.   Click LEFT MOUSE button to COMMIT.",
                level=Qgis.Info,
                duration=7,
            )
            return True
        else:
            return False

    def moveHistogram(self, histo, steps=0):
        histoidx = self.tlvbox.indexOf(histo)
        if steps > 0:
            if histoidx <= 0:
                return False
            else:
                newidx = histoidx - 1
                self.tlvbox.removeWidget(histo)
                self.tlvbox.insertWidget(newidx, histo)
                self.overview.movetimeline(histoidx, newidx)
                self.timeplayer.movelayer(histo.getLayer(), 1)
        elif steps < 0:
            if histoidx >= self.tlvbox.count() - 1:
                return False
            else:
                newidx = histoidx + 1
                self.tlvbox.removeWidget(histo)
                self.tlvbox.insertWidget(newidx, histo)
                self.overview.movetimeline(histoidx, newidx)
                self.timeplayer.movelayer(histo.getLayer(), -1)

    def addtimeline(self, tdl):
        newhisto = HistogramWidget(tdl, self)
        self.histos.append(newhisto)
        hbox = QHBoxLayout()
        hbox.addWidget(newhisto)
        self.tlvbox.insertWidget(0, newhisto)
        newhisto.stackUnder(self.barwidget)
        self.flushUIevents()
        # self.resize()
        return newhisto

    def removetimeline(self, histogram):
        QgsMessageLog.logMessage(
            " Remove timeline: " + histogram.getName(), "QTDC", Qgis.Info
        )
        self.histos.remove(histogram)
        self.tlvbox.removeWidget(histogram)
        self.tlvbox.update()
        self.timeplayer.unload(histogram.datalayer)

    def removeAllTimelines(self):
        for h in self.histos:
            h.setParent(None)

    def histogramDestroyed(self):
        QgsMessageLog.logMessage(
            "...timeline removed. " + str(len(self.histos)) + " remain.",
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

        # when timeline is resized, also resize the histograms of the timeline and overview.
        self.overview.resize()

        # Resize the barwidget and zoomwidget to make the full timeline drawable for them
        self.barwidget.resize(
            self.size().width(), self.size().height() - 16
        )  # Clip the label area (16px) at the bottom
        self.zoomwidget.resize(self.size().width(), self.size().height() - 16)

        # Position the limit buttons to the new size  UNCOMMENT WITH BUTTON CODE IN INIT
        # self.startLimit.setGeometry(0, self.height()-14, 15, 15)
        # self.endLimit.setGeometry(self.width()-15, self.height()-14, 15, 15)

        region = QRegion(self.rect())
        histoct = len(self.histos)
        # Resize the individual histograms and apply a mask to the barwidget for their control geometries
        for h in self.histos:
            QgsMessageLog.logMessage(
                "Histogram position: " + str(h.pos().x()) + ", " + str(h.pos().y()),
                "QTDC",
                Qgis.Info,
            )
            h.setlogscale(self.logscale)
            if (self.max - self.min) > 0:
                h._resize(self.min, self.max, histoct)
                self.pencolor = QtGui.QColor(100, 100, 100)
            else:  # invalid time range, so set pen color to alert user
                self.pencolor = QtGui.QColor(255, 50, 50)
                h._resize(self.min, self.max, histoct)
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
        h = size.height() - 15  # Trim 15 pixels from the bottom for timeline labels

        step = int(round(w / 10.0))  # Get step size across x axis for timeline labels

        pen = QtGui.QPen(self.pencolor, 1, QtCore.Qt.SolidLine)

        qp.setPen(pen)
        qp.setBrush(QtCore.Qt.NoBrush)
        qp.drawRect(0, 0, w - 1, h - 1)

        metrics = qp.fontMetrics()

        qp.drawRect(0, 0, w, h)

        j = 0

        starttick = self.min
        # tick marks and timeline labels for x axis
        for i in range(step, 10 * step, step):

            qp.drawLine(i, h, i, h + 5)
            ticktime = (i / w) * self.range + self.min
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

                # tickstring = time.strftime('%H:%M', time.gmtime(ticktime))
            except Exception as e:
                tickstring = "NaN"
            fw = metrics.width(tickstring)
            qp.drawText(int(i - fw / 2), h + 15, tickstring)

        qp.drawText(17, h + 15, self.startstring)  # Leave gap (17) for limit button

        metrics = qp.fontMetrics()
        fw = metrics.width(self.endstring)
        qp.drawText(
            w - fw - 17, h + 15, self.endstring
        )  # Leave gap (17) for limit button

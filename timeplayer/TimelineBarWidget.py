#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import sys, math, time
from datetime import datetime
import pytz

from qgis.core import QgsMessageLog
from qgis.PyQt import QtGui, QtCore, QtWidgets
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import QWidget


class TimelineBarWidget(QWidget):
    # This is a custom widget to draw a cosmetic element representing the draggable timeline data window.
    def __init__(self, parent, showtimes=True):
        super(TimelineBarWidget, self).__init__(parent)
        self.timeline = parent
        self.linepos = 0
        self.histpos = 0
        self.timestring = ""
        self.historystring = ""
        self.durationstring = ""
        self.showduration = False
        self.tmin = 0
        self.tmax = 0
        self.history = 0
        self.trange = 0
        self.showtimes = showtimes

    def getDurationString(self):
        return self.durationstring

    def showDuration(self, showit):
        self.showduration = showit

    def getPosition(self):
        return self.linepos

    def getHistPosition(self):
        return self.histpos

    def setrange(self, start, end):
        # Set the time range of the timeline for calculating pixel positions along that range
        self.tmin = start
        self.tmax = end  # max not really used
        self.trange = end - start

    def movebar(self, pos):
        # Compute a time value corresponding to a new pixel position and set the time values
        # self.linepos = pos.x()
        size = self.size()
        w = size.width()
        newtime = (((pos.x()) / (w)) * self.trange) + self.tmin
        self.settime(newtime, newtime - self.history)

    def settime(self, t, h):
        # Update the timewindow position according to the time value and
        # the timeline label strings for current and history time.

        self.time = t
        self.history = h
        size = self.size()
        w = size.width()
        # self.linepos = 0
        if self.trange > 0:
            self.linepos = int(
                max(((t - self.tmin) / self.trange) * w, 0)
            )  # clip drawing position to widget area
            self.linepos = int(min(self.linepos, w))
            ht = t - self.history
            self.histpos = int(
                max(((ht - self.tmin) / self.trange) * w, 0)
            )  # clip drawing position to widget area
            self.histpos = int(min(self.histpos, w))
            try:
                self.timestring = (
                    datetime.fromtimestamp(t)
                    .astimezone(pytz.utc)
                    .strftime("%H:%M:%S.%f")[:-4]
                )
                self.historystring = (
                    datetime.fromtimestamp(ht)
                    .astimezone(pytz.utc)
                    .strftime("%H:%M:%S.%f")[:-4]
                )

                self.durationstring, sign = self.timeline.getDynamicTimeString(
                    self.history
                )

            except Exception as e:
                self.timestring = ""
                self.historystring = ""
                self.durationstring = ""

    def reset(self):
        self.linepos = 0
        self.histpos = 0
        self.timestring = ""
        self.historystring = ""
        self.durationstring = ""
        self.tmin = 0
        self.tmax = 0
        self.history = 0
        self.trange = 0

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawwidget(qp)
        qp.end()

    def drawwidget(self, qp):
        # Draw the elements (start/end bars, start/end time labels, time window shading)
        # Shaded box
        size = self.size()
        w = size.width()
        h = size.height()
        pen = QtGui.QPen(QtGui.QColor(100, 100, 100, 70), 2, QtCore.Qt.SolidLine)
        brush = QBrush(QtGui.QColor(150, 150, 150, 50))
        qp.setPen(pen)
        qp.setBrush(brush)
        qp.drawRect(self.histpos, 0, (self.linepos - self.histpos), h)
        # History end line
        pen = QPen(QtGui.QColor(255, 0, 0))
        pen.setWidth(2)
        qp.setPen(pen)
        qp.drawLine(self.histpos, 0, self.histpos, h)
        # Locate the history time string - display at bottom left of history end bar
        metrics = qp.fontMetrics()
        fw = metrics.width(self.historystring)
        fh = metrics.height()
        histtextpos = self.histpos - fw
        if histtextpos < 0:
            histtextpos = self.histpos
        # History start line
        pen = QPen(QtGui.QColor(0, 200, 0))
        qp.setBrush(QtCore.Qt.NoBrush)
        pen.setWidth(2)
        qp.setPen(pen)
        qp.drawLine(self.linepos, 0, self.linepos, h)
        # Locate the current time string - display at top right of current time bar
        metrics = qp.fontMetrics()
        fw = metrics.width(self.timestring)
        fh = metrics.height()
        timetextpos = self.linepos
        if (timetextpos + fw) > w:
            timetextpos = self.linepos - fw

        pen = QtGui.QPen(QtGui.QColor(100, 100, 100), 1, QtCore.Qt.SolidLine)
        yellowpen = QtGui.QPen(QtGui.QColor(200, 200, 50), 1, QtCore.Qt.SolidLine)
        qp.setPen(pen)
        qp.setBrush(brush)

        if self.showtimes:
            brush = QBrush(QtGui.QColor(0, 0, 0, 175))
            blackpen = QtGui.QPen(QtGui.QColor(0, 0, 0), 2, QtCore.Qt.SolidLine)
            qp.setPen(blackpen)
            qp.setBrush(brush)
            # Draw the time strings for history and current time
            # qp.drawRect(histtextpos-2, h-fh-3, fw, fh+3)
            # qp.drawRect(timetextpos+2, 0, fw, fh)
            qp.setPen(pen)
            qp.drawText(histtextpos - 2, h - 5, self.historystring)
            qp.drawText(timetextpos + 2, 10, self.timestring)

        if self.showduration:
            # Draw the duration text box centered on the time window
            dw = metrics.width(self.durationstring)
            durationposition = int(
                self.histpos + ((self.linepos - self.histpos) / 2) - dw / 2
            )

            qp.setPen(blackpen)
            qp.setBrush(brush)
            qp.drawRect(durationposition, int(h / 2 - fh / 2 - 3), dw, fh + 3)

            qp.setPen(yellowpen)
            qp.drawText(durationposition, int(h / 2 + fh / 2 - 3), self.durationstring)

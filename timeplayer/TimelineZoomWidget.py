#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import sys, math, time
from datetime import datetime

from qgis.core import QgsMessageLog
from qgis.PyQt import QtGui, QtCore, QtWidgets
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import QWidget


class TimelineZoomWidget(QWidget):
    # This is a custom widget to draw the draggable timeline bar element.
    def __init__(self, parent=None, linecolor=None):
        super(TimelineZoomWidget, self).__init__(parent)
        self.linepos = 0
        self.histpos = 0
        self.timestring = ""
        self.historystring = ""
        self.min = 0
        self.max = 0
        self.history = 0
        self.range = 0
        if linecolor:
            self.linecolor = linecolor
        else:
            self.linecolor = QtGui.QColor(0, 0, 255)

    def getPosition(self):
        return self.linepos

    def getHistory(self):
        return self.histpos

    def getCenterX(self):
        centerx = None
        diff = self.linepos - self.histpos
        centerx = self.histpos + (diff / 2)
        return centerx

    def move(self, delta):
        self.histpos = self.histpos + delta
        self.linepos = self.linepos + delta

    def place(self, pos):
        # Set the time range of the timeline
        self.histpos = pos.x()
        self.linepos = pos.x()

        # self.min = start
        # self.max = end
        # self.range = end - start

    def stretchBack(self, pos):
        if pos.x() >= self.linepos:
            self.linepos = pos.x() + 1
        self.histpos = pos.x()

    def stretch(self, pos, allowCrossover=False):
        if not allowCrossover and (pos.x() <= self.histpos):
            self.histpos = pos.x() - 1
        self.linepos = pos.x()

        # size = self.size()
        # w = size.width()
        # newtime = (((pos.x())/(w))*self.range)+self.min
        # self.settime(newtime, newtime-self.history)

    # def settime(self, t, h):
    # #Set the time of the timeline and update the timewindow element including
    # #the timeline labels for current and history time.
    # self.time = t
    # self.history = h
    # size = self.size()
    # w = size.width()
    # self.linepos = 0
    # if (self.range>0):
    # self.linepos = ((t-self.min)/self.range)*w
    # ht = t-self.history
    # self.histpos = max(((ht-self.min)/self.range)*w,0)
    # try:
    # self.timestring = datetime.fromtimestamp(t).strftime('%H:%M:%S.%f')[:-4]
    # self.historystring = datetime.fromtimestamp(ht).strftime('%H:%M:%S.%f')[:-4]
    # #self.timestring = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(t)))
    # #self.historystring = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(ht)))
    # except Exception as e:
    # self.timestring = ""
    # self.historystring = ""
    # #print(self.timestring)

    def reset(self):
        self.linepos = 0
        self.histpos = 0
        self.timestring = ""
        self.historystring = ""
        self.min = 0
        self.max = 0
        self.history = 0
        self.range = 0

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
        pen = QPen(self.linecolor)
        pen.setWidth(2)
        qp.setPen(pen)
        qp.drawLine(self.histpos, 0, self.histpos, h)
        # Locate the history time string - display at bottom left of history end bar
        metrics = qp.fontMetrics()
        fw = metrics.width(self.historystring)
        histtextpos = self.histpos - fw
        if histtextpos < 0:
            histtextpos = self.histpos
        # History start line
        # pen = QPen(QtGui.QColor(0, 0, 255))
        pen = QPen(self.linecolor)
        qp.setBrush(QtCore.Qt.NoBrush)
        pen.setWidth(2)
        qp.setPen(pen)
        qp.drawLine(self.linepos, 0, self.linepos, h)
        # #Locate the current time string - display at top right of current time bar
        # metrics = qp.fontMetrics()
        # fw = metrics.width(self.timestring)
        # timetextpos = self.linepos
        # if ((timetextpos + fw) > w):
        # timetextpos = self.linepos - fw

        # pen = QtGui.QPen(QtGui.QColor(20, 20, 20), 1,
        # QtCore.Qt.SolidLine)
        # qp.setPen(pen)
        # qp.setBrush(QtCore.Qt.NoBrush)

        # #Draw the time strings for history and current time
        # qp.drawText(histtextpos, h-5, self.historystring)
        # qp.drawText(timetextpos, 10, self.timestring)

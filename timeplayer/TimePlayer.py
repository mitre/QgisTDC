#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import sys
import os
import time
from datetime import datetime
import pytz
import numpy as np
import gc
import math

from qgis.PyQt import QtGui, QtCore, QtWidgets
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import QWidget, QDialog, QColorDialog
from qgis.utils import iface
from qgis.core import Qgis, QgsPoint, QgsMessageLog, QgsApplication, QgsTask
from qgis.gui import QgsVertexMarker, QgsMapCanvasItem, QgsFileWidget

from .TimeDataPoint import TimeDataPoint
from .TimeDataLayer import TimeDataLayer
from .CanvasTextLayer import CanvasTextLayer

from .LoadLayerProcessor import LoadLayerProcessor
from .LoadLayer import Ui_LoadLayerDialog

from ..QTDC_settings import QTDCsettingsDialog

from .LoadLayerTask import LoadLayerTask


class TimePlayer(QObject):
    """
    This is the controller class for time line and map data animation.
    """

    class TimeAnimator(QObject):
        # This class is a container for the parameter used for time
        def __init__(self):
            super(TimePlayer.TimeAnimator, self).__init__()
            self._ctime = 0

        @pyqtProperty(float)
        def ctime(self):
            return self._ctime

        @ctime.setter
        def ctime(self, value):
            self._ctime = value

    def __init__(self, mainUI):
        super(TimePlayer, self).__init__()

        self.mainUI = mainUI
        self.canvas = mainUI.canvas

        # Connect to the Load Layer dialog to capture inputs from its time field controls
        # self.loadlayerDialog = QDialog()
        # self.loadlayerUI = Ui_LoadLayerDialog()
        # self.loadlayerUI.setupUi(self.loadlayerDialog)
        # self.loadlayerUI.multiplierBox.valueChanged.connect(self.setmultiplier)
        # self.loadlayerUI.timeattributeBox.currentIndexChanged.connect(self.setepochfield)
        # self.loadlayerUI.endTimeAttributeBox.currentIndexChanged.connect(self.setdurationfield)

        # Initialize the layers set and animator settings.
        self.layers = []
        self.time_anim = TimePlayer.TimeAnimator()
        self.anim = QPropertyAnimation(self.time_anim, b"ctime")
        self.anim.setStartValue(1)
        self.anim.setEndValue(1)
        self.anim.setDuration(10000)
        self.anim.setLoopCount(1)
        self.anim.valueChanged.connect(self.showdata)  # called for each animation tick
        self.anim.finished.connect(self.finished)  # called at end of animation
        self.currentTime = 0
        self.lastframe = -1

        # Set up frame animation mode
        self.frameMode = False
        self.intervalTimer = QTimer()
        self.intervalTimer.timeout.connect(
            self.nextFrame
        )  # called when interval timer expires
        self.frameSize = self.mainUI.stepsizeBox.value()

        self.fails = 0

        self.epochfield = 0
        self.epochname = ""
        # self.multiplier = self.loadlayerUI.multiplierBox.value()
        self.history = 0
        self.speed = 1

        self.useplaywindow = False

        self.capture = False
        self.framenum = 0

        # This state variable is needed because normal and frame animation use different animation objects.
        # It is mainly used to prevent uncommanded animation when not animating in repeat mode.
        self.paused = True

        self.mint = sys.maxsize
        self.maxt = -sys.maxsize - 1

        self.statuslayer = CanvasTextLayer(self.canvas)
        self.statuslayer.updateCanvas()
        self.fwd = True
        self.skipgaps = mainUI.skipBox.isChecked()
        self.repeat = mainUI.repeatBox.isChecked()

        self.settingsDialog = QTDCsettingsDialog(self.getMessageBar())
        self.updateSettings()

    @property
    def ctime(self):
        return self.animator.ctime

    @property
    def mintime(self):
        return self.mint

    @property
    def maxtime(self):
        return self.maxt

    def getLayer(self, uid):
        for l in self.layers:
            if uid == l.uid:
                return l
        return None

    def settingsAction(self):
        self.settingsDialog.show()
        self.settingsDialog.exec_()
        self.updateSettings()
        self.showdata()

    def updateSettings(self):
        self.statuslayer.setSize(self.settingsDialog.textSize)
        self.statuslayer.setColor(self.settingsDialog.textColor)
        self.statuslayer.setVisible(self.settingsDialog.showText)
        self.setCaptureFolder(self.settingsDialog.captureFolder)
        self.setCapturePrefix(self.settingsDialog.captureFilePrefix)
        if self.imageFolder and self.imagePrefix:
            self.captureFileRoot = os.path.join(self.imageFolder, self.imagePrefix)
        else:
            self.showMessage("Capture file settings are incomplete.", Qgis.Info, 4)

    def showMessage(self, _text, _level, _duration):
        messagebar = self.getMessageBar()
        messagebar.pushMessage(_text, level=_level, duration=_duration)

    def togglestate(self, v):
        for l in self.layers:
            l.togglestate(v)
        self.statuslayer.setVisible(v)

    def setCapture(self, c):
        self.capture = c
        if self.capture:
            self.showMessage(
                "Frame mode map capture ACTIVATED.  Animation may lag as a result.",
                Qgis.Info,
                3,
            )

    def setCaptureFolder(self, f):
        self.imageFolder = f
        self.framenum = 0

    def setCapturePrefix(self, p):
        if not (p == None):
            self.imagePrefix = p
        else:
            self.imagePrefix = "Image"
        self.framenum = 0

    def setskip(self, skip):
        self.skipgaps = skip

    def setrepeat(self, r):
        self.repeat = r
        QgsMessageLog.logMessage(" Repeat mode: " + str(self.repeat), "QTDC", Qgis.Info)

    # def setFrameCount(self, count):
    # self.anim.setEndValue(count)

    def now(self):
        return self.currentTime

    def finished(self):
        # Callback for when animation reaches the end of data and automatically stops. This fires
        # whenever the animation time is at or past the end time of the animation whether by
        # the animation process or by user intervention.
        if not self.repeat:
            self.mainUI.setplaylabel(True)  # True sets label to 'Play'
        else:
            # Wait briefly before resetting playback (repeat mode only)
            QTimer.singleShot(500, self.resetPlayback)

    def resetPlayback(self):
        if self.fwd:
            if self.useplaywindow:
                self.currentTime = self.playstarttime
            else:
                self.currentTime = self.mint
        else:
            if self.useplaywindow:
                self.currentTime = self.playendtime
            else:
                self.currentTime = self.maxt
        if not self.paused:
            self.animate()

    def addlayer(self, layer):
        self.layers.append(layer)

    def removelayer(self, layer):
        self.layers.remove(layer)

    # def setepochfield(self, ef):
    # self.epochfield = ef
    # self.epochname = self.loadlayerUI.timeattributeBox.currentText()
    # #TODO need to preview time field and attempt parsing when this is called

    # QgsMessageLog.logMessage(" Selected epoch field: "+ self.epochname, 'QTDC')

    # def setdurationfield(self, df):
    # self.durationfield = df
    # self.durationname = self.loadlayerUI.endTimeattributeBox.currentText()
    # #TODO need to preview time field and attempt parsing when this is called

    # QgsMessageLog.logMessage(" Selected duration field: "+ self.durationname, 'QTDC')

    # def setmultiplier(self, m):
    # self.multiplier = m

    def isAnimating(self):
        if self.frameMode:
            return self.intervalTimer.isActive()
        else:
            return self.anim.state() == QAbstractAnimation.Running

    def isStopped(self):
        return self.anim.state() == QAbstractAnimation.Stopped

    def getdata(self):
        # Returnes an merged time index collection for data in all layers
        data = []
        for l in self.layers:
            data.extend(l.gettimeindex())
        return data

    def setDataLimits(self):
        # Establish the time limits of all loaded data and update
        # the animation start and end times and the UI label.
        if len(self.layers) > 0:
            QgsMessageLog.logMessage("Set TIMEPLAYER data limits.", "QTDC", Qgis.Info)
            firstPass = True
            for l in self.layers:
                if not l.isLoading:
                    if firstPass:
                        firstPass = False
                        self.mint = sys.maxsize
                        self.maxt = -sys.maxsize - 1
                    if l.getmintime() < self.mint:
                        self.mint = l.getmintime()
                    if l.getmaxtime() > self.maxt:
                        self.maxt = l.getmaxtime()
            self.setplaystart(self.mint)
            self.setplayend(self.maxt)
            self.updateAnimationSpeed()
            self.mainUI.refreshtimelabel(self.mint, self.maxt)

    def setAnimationMode(self, isFrameMode):
        self.setpause(True)
        self.anim.stop()
        self.intervalTimer.stop()
        self.frameMode = isFrameMode
        self.updateAnimationSpeed()

        # Call setFrameSize for the framesize check to inform user about keeping frame size smaller than history.
        self.setFrameSize(self.frameSize)

        QgsMessageLog.logMessage(
            "Frame Mode is : " + str(self.frameMode), "QTDC", Qgis.Info
        )

    def setFrameSize(self, size):
        if (self.frameMode) and (self.frameSize > self.history):
            self.showMessage(
                "For best results in FRAME mode, frame size should be smaller than the time window duration.",
                Qgis.Info,
                3,
            )
        self.frameSize = size

    def nextFrame(self):
        if self.fwd:
            dir = 1
        else:
            dir = -1
        self.step(self.frameSize * dir)

    def step(self, increment):
        # Called when step buttons are used or when frame timer expires
        t = self.currentTime + float(increment)

        self.setplayposition(t)
        self.showdata(t)

        # If playback is clipped, use the clip limits instead of the data range limits
        if self.mainUI.viewLimitBox.isChecked():
            minlimit = self.playstarttime
            maxlimit = self.playendtime
        else:
            minlimit = self.mint
            maxlimit = self.maxt

        # Capture the display and save it as an image file if capture mode is active
        if self.capture and self.frameMode:
            map_image = QImage(QWidget.grab(self.mainUI.iface.mapCanvas()))
            imageFile = os.path.join(
                self.imageFolder,
                self.imagePrefix + "_" + format(self.framenum, "05d") + ".png",
            )
            saved = map_image.save(imageFile)
            if not saved:
                self.showMessage(
                    "Saving failed for image: "
                    + imageFile
                    + ".  Check settings for map image capture, verify destination folder exists.",
                    Qgis.Warning,
                    5,
                )
            self.framenum += 1

        # The 'finished' signal doesn't fire in frame mode because it uses a different animator
        # Handle frame mode animation repeat here
        if self.frameMode and (not self.paused):

            if self.fwd:
                if t >= maxlimit:
                    if self.repeat:
                        self.intervalTimer.stop()
                        # Add an extra interval before continuing so last frame can display
                        QTimer.singleShot(
                            self.intervalTimer.interval(),
                            lambda: self.resetFramePlay(minlimit),
                        )
                    else:
                        self.setpause(True)
            else:
                if t <= minlimit:
                    if self.repeat:
                        self.intervalTimer.stop()
                        # Add an extra interval before continuing so last frame can display
                        QTimer.singleShot(
                            self.intervalTimer.interval(),
                            lambda: self.resetFramePlay(maxlimit + self.history),
                        )
                    else:
                        self.setpause(True)
        # else:
        # self.setpause(True)

    def resetFramePlay(self, t):
        self.currentTime = t
        self.intervalTimer.start()

    def setMinMaxTimes(self, pendingLayer=None):
        firstPass = True
        if pendingLayer is not None:
            firstPass = False
            self.mint = sys.maxsize
            self.maxt = -sys.maxsize - 1
            self.mint = min(pendingLayer.getmintime(), self.mint)
            self.maxt = max(pendingLayer.getmaxtime(), self.maxt)
        # self.mint = sys.maxsize
        # self.maxt = -sys.maxsize - 1
        for l in self.layers:
            # Skip layers that are loading
            if not l.isLoading:
                if firstPass:
                    firstPass = False
                    self.mint = sys.maxsize
                    self.maxt = -sys.maxsize - 1

                self.mint = min(l.getmintime(), self.mint)
                self.maxt = max(l.getmaxtime(), self.maxt)

    def updated(self, timedatalayer):
        # Make sure layer wasn't removed by user during update
        if timedatalayer in self.layers:
            self.setMinMaxTimes(timedatalayer)
            if not self.mainUI.viewLimitBox.isChecked():
                self.setplaystart(self.mint)
                self.setplayend(self.maxt)
        self.loadfinisher(timedatalayer, True)
        timedatalayer.setLoading(False)
        self.step(0)
        QgsMessageLog.logMessage(
            "TIMEPLAYER updated " + timedatalayer.getName(), "QTDC", Qgis.Info
        )

    def reloadmaplayer(self, timedatalayer):
        QgsMessageLog.logMessage(
            "*****************  Request to reload layer " + timedatalayer.getName(),
            "QTDC",
            Qgis.Info,
        )

        maplayer = timedatalayer.maplayer
        if maplayer.featureCount() > 0:
            timedatalayer.setLoading(True)
            timedatalayer.resetData()
            # Spawn a task to perform the actual loading of data into the layer.
            # self.update is called when done since this is a reload and the existing timeline is re-used
            reloader = LoadLayerTask(
                "Loading " + maplayer.name(), maplayer, timedatalayer, self.updated
            )
            QgsApplication.taskManager().addTask(reloader)
        else:
            self.showMessage(
                timedatalayer.getName()
                + " returned NO LOADABLE FEATURES.  Check the layer filter setting.",
                Qgis.Warning,
                4,
            )

    def loadmaplayer(self, maplayer, loadfinisher, preApproved):
        self.loadfinisher = (
            loadfinisher  # The load finisher is called by our loadingComplete method
        )
        layerloader = LoadLayerProcessor(self.canvas)
        loadstate, approved = layerloader.load(maplayer, preApproved)

        if loadstate:
            QgsMessageLog.logMessage(
                "************************ Load state: " + loadstate.asString(),
                "QTDC",
                Qgis.Info,
            )

            timedatalayer = TimeDataLayer(self.canvas, maplayer, loadstate)

            timedatalayer.layerUpdate.connect(self.updated)
            timedatalayer.layerReload.connect(self.reloadmaplayer)

            gc.collect()  # garbage collection

            # Spawn a task to perform the actual loading of data into the layer.  self.loadingComplete is called when done.
            loader = LoadLayerTask(
                "Loading " + maplayer.name(),
                maplayer,
                timedatalayer,
                self.loadingComplete,
            )
            QgsApplication.taskManager().addTask(loader)
        else:
            self.loadingComplete()
        return approved

    def getMessageBar(self):
        return self.mainUI.iface.messageBar()

    def loadingComplete(self, timedatalayer=None):
        # This method is called once the layer data loading task has finished, to update some limit parameters.
        if timedatalayer:
            self.anim.stop()
            timedatalayer.setMessageBar(self.mainUI.iface.messageBar())
            QgsMessageLog.logMessage(" LOADING COMPLETE!!", "QTDC", Qgis.Info)
            if timedatalayer.success:
                QgsMessageLog.logMessage(
                    "Min time: " + str(timedatalayer.getmintime()), "QTDC", Qgis.Info
                )
                QgsMessageLog.logMessage(
                    "Max time: " + str(timedatalayer.getmaxtime()), "QTDC", Qgis.Info
                )
                self.mint = min(timedatalayer.getmintime(), self.mint)
                self.maxt = max(timedatalayer.getmaxtime(), self.maxt)
                if not self.mainUI.viewLimitBox.isChecked():
                    self.setplaystart(self.mint)
                    self.setplayend(self.maxt)
                self.layers.append(timedatalayer)
                QgsMessageLog.logMessage(
                    " TIME RANGE: "
                    + str(self.anim.startValue())
                    + " : "
                    + str(self.anim.endValue()),
                    "QTDC",
                    Qgis.Info,
                )
                self.loadfinisher(timedatalayer, False)
            else:
                self.canvas.scene().removeItem(timedatalayer)

            return timedatalayer
        gc.collect()
        return timedatalayer

    def reset(self):
        # Clear the layerset and time limits
        self.mint = sys.maxsize
        self.maxt = -sys.maxsize - 1
        self.clear(self.canvas)
        self.layers = []

    def showdata(self, t=None):
        # Display data at given time.
        if not t:
            t = self.currentTime
        if t:
            self.currentTime = t
            self.mainUI.settime(t, self.history)
            self.statuslayer.clear()
            if self.skipgaps and self.isAnimating() and (not self.frameMode):
                skiptimelist = []
                # Iterate through the layerset and display each layer at given time
                for l in self.layers:
                    ndi = l.settime(t)
                    # If non-zero no data index, add it to the skip time list
                    if ndi > 0:
                        skiptimelist.append(ndi)
                    else:
                        l.updateCanvas()

                if len(skiptimelist) > 0:
                    # If every layer returned a skip time index, no data was found for current time, skip to data time depending on play direction
                    if len(self.layers) == len(skiptimelist):
                        sortedlist = sorted(skiptimelist)
                        tindex = np.searchsorted(sortedlist, t, side="left")
                        if not self.fwd:
                            tindex = max(tindex - 1, 0)
                            datatime = sortedlist[tindex] + self.history
                        else:
                            tindex = min(tindex, len(sortedlist) - 1)
                            datatime = sortedlist[tindex]
                        self.setplayposition(datatime)

            else:
                # Iterate through the layerset and display each layer at given time
                for l in self.layers:
                    foo = l.settime(
                        t
                    )  # foo is the next data index to be ignored since we are not skipping gaps
                    l.updateCanvas()

            # Show displayed data time info on the canvas
            try:
                tstart = max((t - self.history), 0)
                starttime = datetime.fromtimestamp(tstart).astimezone(pytz.utc)
                start_ts = starttime.strftime("%Y-%m-%d %H:%M:%S.%f")[
                    :-4
                ]  # slice off last 4 digits to get 2 decimal places
                endtime = datetime.fromtimestamp(t).astimezone(pytz.utc)
                end_ts = endtime.strftime("%Y-%m-%d %H:%M:%S.%f")[
                    :-4
                ]  # slice off last 4 digits to get 2 decimal places

                ts = "TDC : " + start_ts + "   " + end_ts
                self.fails = 0
                self.statuslayer.setmessage(ts)
            except Exception as e:
                self.fails += 1
                # QgsMessageLog.logMessage(str(e), "QTDC")
                pass  # can happen a lot with no serious consequenses

    def setplaywindow(self, start, end):
        if self.mainUI.viewLimitBox.isChecked():
            QgsMessageLog.logMessage("SET play window", "QTDC", Qgis.Info)
            clipstart = max(start, self.mint)
            clipend = min(end, self.maxt)
            self.playstarttime = clipstart
            self.playendtime = clipend
            self.setplaystart(clipstart)
            self.setplayend(clipend)
            self.useplaywindow = True
            self.updateAnimationSpeed()
            # self.mainUI.refreshtimelabel(start, end)
        pass

    def clearplaywindow(self):
        self.setplaystart(self.mint)
        self.setplayend(self.maxt)
        self.updateAnimationSpeed()
        self.useplaywindow = False
        pass

    def setplayposition(self, t):
        # Set current time of animator to resume animation at specified time.
        # Actual animator time is computed from requested time, time range and playback full duration
        if self.useplaywindow:
            # Make sure t is within the playback range
            if t > self.playendtime:
                t = self.playendtime
            if t < self.playstarttime:
                t = self.playstarttime

            trange = self.playendtime - self.playstarttime
            if trange > 0:
                newpos = (t - self.playstarttime) / trange * self.anim.duration()
                self.anim.setCurrentTime(int(newpos))
        else:
            # Make sure t is within the playback range
            if t > self.maxt:
                t = self.maxt
            if t < self.mint:
                t = self.mint

            trange = self.maxt - self.mint
            if trange > 0:
                newpos = (t - self.mint) / trange * self.anim.duration()
                if newpos > self.anim.duration():
                    newpos = self.anim.duration()
                self.anim.setCurrentTime(int(newpos))

    def movelayer(self, layer, dir):
        layerindex = self.layers.index(layer)
        if dir > 0:
            if layerindex + 1 <= len(self.layers) - 1:
                self.layers[layerindex], self.layers[layerindex + 1] = (
                    self.layers[layerindex + 1],
                    self.layers[layerindex],
                )
        else:
            if layerindex > 0:
                self.layers[layerindex], self.layers[layerindex - 1] = (
                    self.layers[layerindex - 1],
                    self.layers[layerindex],
                )

        # re-order layers on the canvas
        for l in self.layers:
            self.canvas.scene().removeItem(l)
        for l in self.layers:
            self.canvas.scene().addItem(l)

    def unload(self, layer):
        self.anim.stop()
        # aState = self.anim.state()
        # if aState == QAbstractAnimation.Stopped:
        # QgsMessageLog.logMessage("ANIMATION HAS STOPPED", "DEBUG")
        # else:
        # QgsMessageLog.logMessage("DANGER ****  ANIMATION NOT STOPPED  ****  DANGER", "DEBUG")
        self.intervalTimer.stop()
        self.layers.remove(layer)
        self.canvas.scene().removeItem(layer)
        self.mint = sys.maxsize
        self.maxt = -sys.maxsize - 1
        for l in self.layers:
            if not l.isLoading:
                self.mint = min(l.getmintime(), self.mint)
                self.maxt = max(l.getmaxtime(), self.maxt)
        if self.useplaywindow:
            self.setplaystart(self.playstarttime)
            self.setplayend(self.playendtime)
        else:
            self.setplaystart(self.mint)
            self.setplayend(self.maxt)
        self.mainUI.refreshtimelabel(self.mint, self.maxt)
        self.step(0)

    def setplaystart(self, t):
        self.anim.setStartValue(t)

    def setplayend(self, t):
        self.anim.setEndValue(t)

    def animate(self):
        self.paused = False
        if self.frameMode:
            self.intervalTimer.start()
        else:
            starttime = self.currentTime
            self.anim.start()
            self.setplayposition(starttime)

    def animatefrom(self, t):
        self.animate()
        self.anim.ctime = t

    def currentframefilter(self):
        for l in self.layers:
            l.filtervisible()

    def setpause(self, p):
        self.paused = p

        if self.frameMode:
            if p:
                self.intervalTimer.stop()
            else:
                self.intervalTimer.start()
        else:
            self.anim.setPaused(p)
        self.mainUI.setplaylabel(p)

    def setspeed(self, s):
        self.speed = s
        self.updateAnimationSpeed()

    def setdirection(self, d):
        self.fwd = d
        if d:
            self.anim.setDirection(QAbstractAnimation.Forward)
        else:
            self.anim.setDirection(QAbstractAnimation.Backward)

        for l in self.layers:
            l.setdirection(d)

    def updateAnimationSpeed(self):
        # When the speed slider is adjusted, the animation speed is set by modifying its duration/interval parameter.

        if self.frameMode:
            speed = self.speed + 1
            self.mainUI.speedLabel.setText("Playback speed: " + str(speed) + " F/S")
            self.mainUI.stepLabel.setText("Frame")
            self.intervalTimer.setInterval((1 / speed) * 1000)
            self.mainUI.speedLabel.setStyleSheet("color : grey")
        else:
            self.mainUI.stepLabel.setText("Step:")
            speed = 2**self.speed
            old_duration = self.anim.duration()
            old_time = self.anim.currentTime()
            duration = self.anim.endValue() - self.anim.startValue()

            minspeed = int(
                duration / 2073600
            )  # Constant is seconds in 24 days, limit imposed by qt animation framework

            # Times are stored as seconds so convert duration to milliseconds for animator
            duration = int((duration / speed) * 1000)
            if (duration > 100) and (
                speed > minspeed
            ):  # protect against underspeed or  UI runaway due to overspeed
                self.anim.setDuration(duration)
                self.mainUI.speedLabel.setText("Playback speed: " + str(speed) + "X")
                self.mainUI.speedLabel.setStyleSheet("color : grey")
                new_time = old_time
                if old_duration != 0:
                    new_time = old_time * (duration / old_duration)
                self.anim.setCurrentTime(int(new_time))
            elif minspeed > 0:
                # self.mainUI.speedSlider.setMinimum(0)
                speedsetting = math.ceil(math.log(minspeed) / math.log(2)) + 1
                self.mainUI.speedLabel.setStyleSheet("color : red")
            else:
                self.mainUI.speedLabel.setStyleSheet("color : red")

    def sethistory(self, h):
        # Apply the history time setting to all layers in the layerset
        self.history = h
        for l in self.layers:
            l.sethistory(h)
        # Call setFrameSize for the framesize check to inform user about keeping frame size smaller than history.
        self.setFrameSize(self.frameSize)

    def adjusthistory(self, h):
        self.mainUI.adjusthistory(h)

    def gethistory(self):
        return self.history

    def clear(self, canvas):
        # Clear the timeplayer of layers and remove all layers from the map
        self.anim.stop()
        self.lastframe = -1
        for l in self.layers:
            canvas.scene().removeItem(l)
        # self.setFrameCount(0)
        self.mint = sys.maxsize
        self.maxt = -sys.maxsize - 1
        self.layers = []

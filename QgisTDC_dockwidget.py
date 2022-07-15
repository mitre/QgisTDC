# -*- coding: utf-8 -*-
#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

"""
Qgis Time Data Control

A plugin that provides a control panel for animating vector layers that have time stamp attributes..

"""


import os, sys, math, time, traceback

from configparser import ConfigParser

from qgis.PyQt import QtGui, QtCore, QtWidgets, uic
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *

from qgis.PyQt.QtWidgets import (
    QDialog,
    QAction,
    QSlider,
    QHBoxLayout,
    QVBoxLayout,
    QShortcut,
    QMessageBox,
    QSizePolicy,
)

from qgis import utils
from qgis.utils import iface
from qgis.gui import QgsMapCanvasItem
from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsTask,
    QgsApplication,
    QgsProject,
    QgsVectorLayer,
)

# from .timeplayer import TimeDataPoint
from .timeplayer import TimePlayer

# from .timeplayer import TimeDataLayer
from .timeplayer import TimelineWidget
from .timeplayer import TimelineOverviewWidget
from .timeplayer.TimeWindowSettings_ import TimeWindowSettingsDialog

from .timeplayer.LoadLayerTask import LoadLayerTask
from .timeplayer.GeometryTypes import geometryTypes
from .QTDC_API import QTDC_API
from .HTMLContainer import HTMLContainer

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "QgisTDC_dockwidget_base.ui")
)


class QTDC_DockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    timefactor = {"Sec": 1, "Min": 60, "Hour": 3600, "Day": 86400}

    setTimeSignal = pyqtSignal()

    def __init__(self, interface, parent=None):
        """Constructor."""
        super(QTDC_DockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        self.setupUi(self)

        # Set up the UI by initializing the controls and connecting the various actions
        self.iface = interface
        self.canvas = self.iface.mapCanvas()

        self.setStyleSheet("QPushButton { border-color: grey; font-color: grey }")

        self.timeplayer = TimePlayer.TimePlayer(self)

        self.hotkeyButton.clicked.connect(self.showHotkeys)
        self.hotkeyButton.setToolTip("Timeline interaction info")
        self.TDCsettingsButton.clicked.connect(self.timeplayer.settingsAction)
        self.helpButton.clicked.connect(self.showHelp)

        self.loadButton.clicked.connect(self.loadLayer)

        self.playshortcut = QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Z), self)
        self.playshortcut.activated.connect(self.play)

        self.goButton.clicked.connect(self.play)
        self.stepButton.clicked.connect(self.step)
        self.backButton.clicked.connect(self.backstep)

        self.zoomfullButton.clicked.connect(self.zoomfull)

        self.playfwdicon = QIcon(os.path.dirname(__file__) + "/icons/play.png")
        self.playbckicon = QIcon(os.path.dirname(__file__) + "/icons/playback.png")
        self.pauseicon = QIcon(os.path.dirname(__file__) + "/icons/pause.png")

        timeunitnames = list(self.timefactor.keys())
        self.historyUnitsBox.clear()
        self.historyUnitsBox.addItems(timeunitnames)
        # self.historyUnitsBox.setCurrentIndex(1) #Initialize to minutes
        self.stepUnitsBox.clear()
        self.stepUnitsBox.addItems(timeunitnames)

        self.TimeWindowSettingsDialog = TimeWindowSettingsDialog()
        self.timeWindowSettings.clicked.connect(self.manualTimeWindowSetting)

        self.viewLimitBox.clicked.connect(self.setViewLimit)

        self.speedSlider.valueChanged.connect(self.timeplayer.setspeed)
        self.historyBox.valueChanged.connect(self.sethistory)
        self.historyUnitsBox.currentIndexChanged.connect(self.sethistoryunits)
        self.skipBox.clicked.connect(self.timeplayer.setskip)
        self.repeatBox.clicked.connect(self.timeplayer.setrepeat)
        self.frameModeBox.clicked.connect(self.setFrameMode)

        # Set up the custom timeline widget on the UI.  A generic widget
        # was created in QtDesigner that will contain it (timelineBaseWidget).

        self.overview = TimelineOverviewWidget.TimelineOverviewWidget(self.timeplayer)
        hOVbox = QHBoxLayout()
        hOVbox.setContentsMargins(0, 0, 0, 0)
        hOVbox.addWidget(self.overview)
        vOVbox = QVBoxLayout()
        vOVbox.setContentsMargins(0, 0, 0, 0)
        vOVbox.addLayout(hOVbox)
        self.overviewBaseWidget.setLayout(vOVbox)
        self.overviewBaseWidget.setStyleSheet("border: 1px solid rgb(100,100,100)")

        self.timeline = TimelineWidget.TimelineWidget(self.timeplayer, self.overview)
        self.logscaleBox.clicked.connect(self.timeline.logcheck)
        self.stepsizeBox.valueChanged.connect(self.setStep)
        self.stepUnitsBox.currentIndexChanged.connect(self.setstepunits)
        self.timeline.setStep(self.stepsizeBox.value())
        hbox = QHBoxLayout()
        hbox.addWidget(self.timeline)
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        self.timelineBaseWidget.setLayout(vbox)

        self.direction = True

        self.captureButton.clicked.connect(self.timeplayer.setCapture)

        self.visibilityChanged.connect(self.visibility)
        self.unloading = False

        self.totalframes = 0
        self.epochfield = ""

        # Help
        helpicon = QIcon(os.path.dirname(__file__) + "/icons/about20.png")
        self.helpAction = QAction(helpicon, "Help", self.iface.mainWindow())
        self.helpAction.setObjectName("qtdcHelp")
        self.helpAction.triggered.connect(self.showHelp)
        self.iface.addPluginToMenu("QTDC", self.helpAction)

        self.hotkeydlg = QMessageBox(self)
        self.hotkeydlg.setWindowTitle("QTDC Timeline Interactions")
        self.hotkeydlg.setModal(False)
        self.hotkeydlg.setText(HTMLContainer.timeline)

        # Apparently, we need to get this reference in the plugin's __init__ for the load task to run.
        # Without it, Qgis may crash on task start or the task may fail to run.
        # ******  DO NOT REMOVE THE FOLLOWING LINE!  ******
        self.tm = QgsApplication.taskManager()

        self.setWindowTitle("QGIS Time Data Control")

        # Set window title using version number from metadata.txt
        # parser = ConfigParser()
        # parser.read(os.path.join(os.path.dirname(__file__), "metadata.txt"))
        # self.setWindowTitle("QTDC " + parser["general"]["version"])

        self.sethistoryunits()
        self.setstepunits()

    def getAPI(self):
        return QTDC_API(self)

    def showHelp(self):
        QgsMessageLog.logMessage("calling showPluginHelp...", "QTDC", Qgis.Info)
        try:
            utils.showPluginHelp("QgisTDC")
            QgsMessageLog.logMessage("showPluginHelp was called.", "QTDC", Qgis.Info)
        except Exception as helpex:
            QgsMessageLog.logMessage(
                "Show help FAILED: " + str(helpex), "QTDC", Qgis.Warning
            )

    def manualTimeWindowSetting(self):
        self.timeplayer.setpause(True)  # Stop animation if playing
        dt = QDateTime()
        if not self.TimeWindowSettingsDialog.initialized:
            # Set the start time field value
            dt.setSecsSinceEpoch(self.timeplayer.now() - self.timeplayer.gethistory())
            self.TimeWindowSettingsDialog.startTimeEdit.setTimeSpec(
                Qt.UTC
            )  # Displayed times are UTC
            self.TimeWindowSettingsDialog.startTimeEdit.setDateTime(dt.toUTC())
            # Set the end time field value
            dt.setSecsSinceEpoch(self.timeplayer.now())
            self.TimeWindowSettingsDialog.endTimeEdit.setTimeSpec(
                Qt.UTC
            )  # Displayed times are UTC
            self.TimeWindowSettingsDialog.endTimeEdit.setDateTime(dt.toUTC())
            self.TimeWindowSettingsDialog.initialized = True

        originalStartTime = self.TimeWindowSettingsDialog.startTimeEdit.dateTime()
        originalEndTime = self.TimeWindowSettingsDialog.endTimeEdit.dateTime()
        self.TimeWindowSettingsDialog.show()
        result = self.TimeWindowSettingsDialog.exec_()
        if result:
            QgsMessageLog.logMessage("Got settings", "QTDC", Qgis.Info)
            dt = self.TimeWindowSettingsDialog.startTimeEdit.dateTime()
            starttime = dt.toSecsSinceEpoch()
            dt = self.TimeWindowSettingsDialog.endTimeEdit.dateTime()
            endtime = dt.toSecsSinceEpoch()
            if endtime > starttime:

                newhistory = endtime - starttime
                self.adjusthistory(newhistory)
                self.settime(endtime, newhistory)

                # self.timeplayer.sethistory(newhistory)
                # self.timeline.settime(endtime, newhistory)
                self.timeplayer.showdata(endtime)
                # self.overview.settime(endtime, newhistory)
            else:
                # A bad entry was made, so restore the original dialog values
                self.TimeWindowSettingsDialog.startTimeEdit.setDateTime(
                    originalStartTime
                )
                self.TimeWindowSettingsDialog.endTimeEdit.setDateTime(originalEndTime)
                iface.messageBar().pushMessage(
                    "Time window start time must be less than end time.",
                    level=Qgis.Info,
                    duration=5,
                )

    def showHotkeys(self):
        self.hotkeydlg.show()

    def shutdown(self):
        # When Qgis exits, clear the timelines for a clean exit (prevents a Qgis crash)
        self.timeline.removeAllTimelines()
        self.unloading = True

    def visibility(self, visible):
        if not self.unloading:
            self.timeplayer.togglestate(visible)

    def setFrameMode(self, state):
        self.timeplayer.setAnimationMode(state)
        self.skipBox.setEnabled(not state)  # disable the skip box when in frame mode
        self.captureButton.setEnabled(state)  # Only allow capture in frame mode

    def setViewLimit(self):
        self.timeplayer.setpause(True)
        if self.viewLimitBox.isChecked():
            self.timeline.resumeplaywindow()
        else:
            QgsMessageLog.logMessage("CLEAR play window limit", "QTDC", Qgis.Info)
            self.timeplayer.setplaywindow(
                self.timeplayer.mintime, self.timeplayer.maxtime
            )
            self.timeplayer.clearplaywindow()

    def zoomfull(self, e):
        self.timeline.setrange(self.timeplayer.mintime, self.timeplayer.maxtime)
        self.timeline.resize()
        self.timeline.update()
        self.timeplayer.step(0)

    def settime(self, t, history):
        # Update the time of the time line and the time window message on the UI
        self.timeline.settime(t, history)
        durationtext = self.timeline.getDurationString()
        self.durationLabel.setText("Time window duration: " + durationtext)

        self.overview.settime(t, history)
        self.setTimeSignal.emit()

    def sethistory(self, hist):
        h = hist * self.historyfactor
        self.timeplayer.sethistory(h)
        current_time = self.timeplayer.now()
        self.timeline.settime(current_time, h)
        self.timeplayer.showdata(current_time)

    def adjusthistory(self, hist):
        # This method is used to programmatically modify the history box value
        # taking into account the units setting
        h = hist / self.historyfactor
        self.historyBox.setValue(h)

    def sethistoryunits(self):
        historyunits = self.historyUnitsBox.currentText()
        try:
            originalfactor = self.historyfactor
        except:
            originalfactor = self.timefactor.get(historyunits, 1)
        self.historyfactor = self.timefactor.get(historyunits, 1)
        historyvalue = self.historyBox.value()
        self.historyBox.setValue(historyvalue * (originalfactor / self.historyfactor))

    def setStep(self, step):
        s = step * self.stepfactor
        QgsMessageLog.logMessage(str(s) + "  set step", "QTDC", Qgis.Info)
        self.timeline.setStep(s)
        self.timeplayer.setFrameSize(s)

    def setstepunits(self):
        stepunits = self.stepUnitsBox.currentText()
        try:
            originalfactor = self.stepfactor
        except:
            originalfactor = self.timefactor.get(stepunits, 1)
        self.stepfactor = self.timefactor.get(stepunits, 1)
        stepvalue = self.stepsizeBox.value()
        self.stepsizeBox.setValue(stepvalue * (originalfactor / self.stepfactor))

    def resizeEvent(self, e):
        # Catch resize events and send them to the timeline for resizing.
        self.timeline.resize()

    def loadLayer(self):
        # Load the active layer(s) from the map
        selectedlayers = iface.layerTreeView().selectedLayers()
        mbox = QMessageBox()
        mbox.setIcon(QMessageBox.Information)
        if len(selectedlayers) > 0:
            notLoadable = []
            preApproved = False
            for layer in selectedlayers:
                if isinstance(layer, QgsVectorLayer):
                    if layer.wkbType() in geometryTypes.supportedGeometries:
                        preApproved = self.timeplayer.loadmaplayer(
                            layer, self.completeLoading, preApproved
                        )
                        QgsMessageLog.logMessage(
                            str(preApproved) + "  ANR", "QTDC", Qgis.Info
                        )
                    else:
                        notLoadable.append(layer.name())
                else:
                    notLoadable.append(layer.name())
            if len(notLoadable) > 0:
                message = "The following layers do not have supported geometries and cannot be loaded on the TDC:\n"
                for lname in notLoadable:
                    message = message + "\n" + lname
                mbox.setText(message)
                ret = mbox.exec_()
        else:
            mbox.setText("Select layer(s) to load in the layer pane.")
            ret = mbox.exec_()

    def completeLoading(self, tdlayer, updateOnly):
        # This method is called at the completion of the layer load task
        if tdlayer:
            if updateOnly:
                self.overview.setextent(
                    self.timeplayer.mintime, self.timeplayer.maxtime
                )
                self.overview.refreshrange()
                if self.timeline.histocount() == 1:
                    QgsMessageLog.logMessage(
                        "Setting timeline range from dockwindow.", "QTDC", Qgis.Info
                    )
                    self.timeline.clearjournal()
                    self.timeline.setrange(
                        self.timeplayer.mintime, self.timeplayer.maxtime
                    )
                    self.timeline.resize()
                self.refreshtimelabel(self.timeplayer.mintime, self.timeplayer.maxtime)
                self.resize(
                    self.width(), self.height() + 1
                )  # A kludgey way to get timeline to initialize size properly, but it works
            else:
                if tdlayer.success:
                    # If the layer was loaded, set timeplayer and data limit parameters
                    histogram = self.timeline.addtimeline(tdlayer)
                    self.overview.addtimeline(tdlayer, histogram)
                    self.overview.setextent(
                        self.timeplayer.mintime, self.timeplayer.maxtime
                    )
                    self.overview.refreshrange()
                    self.timeplayer.sethistory(
                        self.historyBox.value() * self.historyfactor
                    )
                    self.timeplayer.setspeed(self.speedSlider.value())
                    if self.timeline.histocount() == 1:
                        QgsMessageLog.logMessage(
                            "Setting timeline range from dockwindow.", "QTDC", Qgis.Info
                        )
                        self.timeline.clearjournal()
                        self.timeline.setrange(
                            self.timeplayer.mintime, self.timeplayer.maxtime
                        )
                        self.timeline.resize()
                    else:
                        self.timeplayer.step(0)
                    self.refreshtimelabel(
                        self.timeplayer.mintime, self.timeplayer.maxtime
                    )

                    self.resize(
                        self.width(), self.height() + 1
                    )  # A kludgey way to get timeline to initialize size properly, but it works

                    if tdlayer.loadStatusMessage:
                        iface.messageBar().pushMessage(
                            tdlayer.loadStatusMessage, level=Qgis.Info, duration=5
                        )

                    # Turn off map layer visibility for the loaded layer
                    layerid = tdlayer.maplayer.id()
                    QgsProject.instance().layerTreeRoot().findLayer(
                        layerid
                    ).setItemVisibilityChecked(False)

        self.setplaylabel(not self.timeplayer.isAnimating())

    def refreshtimelabel(self, tmin, tmax):
        try:
            if self.timeline.histocount() >= 1:
                self.overview.setextent(
                    self.timeplayer.mintime, self.timeplayer.maxtime
                )
                self.overview.refreshrange()
            start_ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(tmin))
            end_ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(tmax))
            ts = "Full timeline range: " + start_ts + " :  " + end_ts
            rangeseconds = tmax - tmin
            minimumspeed = int(
                rangeseconds / 2073600
            )  # Constant is seconds in 24 days, limit imposed by qt animation framework
            if minimumspeed > 0:
                self.speedLabel.setStyleSheet("color : red")
            else:
                self.speedLabel.setStyleSheet("color : black")
            self.tdcLabel.setText(ts)
        except Exception as e:
            self.tdcLabel.setText("Timeline range error. ")
            traceString = "".join(traceback.format_exception(None, e, e.__traceback__))
            QgsMessageLog.logMessage(
                "Timeline range error:  " + traceString, "QTDC", Qgis.Info
            )

    def reset(self):
        # Clear the timeplayer of all data and reset parameters
        self.timeplayer.clear(self.canvas)
        self.timeline.reset()
        self.timeline.update()
        self.totalframes = 0
        self.tdcLabel.setText("Reset.")

    def setplaylabel(self, paused):
        # Set the label on the play button according to play state
        if paused:
            if self.direction:
                self.goButton.setIcon(self.playfwdicon)
            else:
                self.goButton.setIcon(self.playbckicon)
        else:
            self.goButton.setIcon(self.pauseicon)

    def play(self):
        # TODO: Add handling for frame mode
        # Start animating.  Take appropriate action depending on the state of the animator (paused, animating or stopped).
        animating = self.timeplayer.isAnimating()
        self.setplaylabel(animating)

        QgsMessageLog.logMessage(
            "Animation state: " + str(animating), "QTDC", Qgis.Info
        )

        if not animating:
            if self.timeplayer.isStopped:
                self.timeplayer.animate()  # Restart animation if stopped
            else:
                self.timeplayer.setpause(animating)  # False un-pauses animation
        else:
            self.timeplayer.setpause(animating)  # True pauses animation

    def step(self):
        # Step the timeplayer forward by the setting of the stepsizeBox
        inc = self.stepsizeBox.value() * self.stepfactor
        if self.direction == False:
            inc = 0
        self.direction = True
        if not self.timeplayer.isAnimating():
            self.goButton.setIcon(self.playfwdicon)
        self.timeplayer.setdirection(self.direction)
        self.timeplayer.step(inc)

    def backstep(self):
        # Step the timeplayer backward by the setting of stepsizeBox
        inc = -self.stepsizeBox.value() * self.stepfactor
        if self.direction == True:
            inc = 0
        self.direction = False
        if not self.timeplayer.isAnimating():
            self.goButton.setIcon(self.playbckicon)
        self.timeplayer.setdirection(self.direction)
        self.timeplayer.step(inc)

    def closeEvent(self, event):
        # Default processing when plugin is closed
        self.closingPlugin.emit()
        event.accept()

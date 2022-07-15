#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import json

from qgis.PyQt import QtCore
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsSettings
from .LayerSettings import Ui_LayerSettingsDialog


class LayerSettingsEditor:

    # The keys will be the selections in the timeunitBox on the UI
    timefactor = {"Sec": 1, "Min": 60, "Hour": 3600, "Day": 86400}

    def __init__(self, canvas, layer, dolabels=False, isline=False):
        super(LayerSettingsEditor, self).__init__()

        self.layer = layer
        self.settingsDialog = QDialog(canvas)
        self.layerSettingsUI = Ui_LayerSettingsDialog()
        self.layerSettingsUI.setupUi(self.settingsDialog)
        self.settings = {
            "dolabels": False,
            "hispeed": False,
            "recentlabels": False,
            "labeltime": 10,
            "labelsize": 10,
            "fademode": False,
            "labeloffsets": [10, 10, 10, False],
        }

        self.layerSettingsUI.endpointBox.setVisible(isline)
        self.layerSettingsUI.labeltimeBox.valueChanged.connect(self.timeAdjustment)

        timeunitnames = list(self.timefactor.keys())
        self.layerSettingsUI.timeunitBox.clear()
        self.layerSettingsUI.timeunitBox.addItems(timeunitnames)
        self.layerSettingsUI.timeunitBox.currentTextChanged.connect(self.unitAdjustment)
        self.unitAdjustment()

        self.s = QgsSettings()
        self.readSettings(dolabels)

    def timeAdjustment(self, t):
        QgsMessageLog.logMessage(
            "Time adjusted " + str(t * self.labelTimeFactor), "QTDC", Qgis.Info
        )

    def unitAdjustment(self):
        QgsMessageLog.logMessage("Unit adjusted", "QTDC", Qgis.Info)
        timeunit = self.layerSettingsUI.timeunitBox.currentText()
        try:
            originalTimeFactor = self.labelTimeFactor
        except:
            originalTimeFactor = self.timefactor.get(timeunit, 1)
        self.labelTimeFactor = self.timefactor.get(timeunit, 1)
        newTimeSetting = self.layerSettingsUI.labeltimeBox.value() * (
            originalTimeFactor / self.labelTimeFactor
        )
        self.layerSettingsUI.labeltimeBox.setValue(newTimeSetting)

    def readSettings(self, dolabels=False):

        try:
            textsettings = self.s.value("QgisTDC/layer_settings", "")
            QgsMessageLog.logMessage(
                "Layer settings." + textsettings, "QTDC", Qgis.Info
            )
            self.settings = json.loads(textsettings)
            QgsMessageLog.logMessage("Settings read in as: ", "QTDC", Qgis.Info)
            QgsMessageLog.logMessage(str(self.settings), "QTDC", Qgis.Info)
            if dolabels:
                self.settings["dolabels"] = True
            QgsMessageLog.logMessage("READ settings.", "QTDC", Qgis.Info)
        except:
            QgsMessageLog.logMessage(
                "Unable to read layer settings.", "QTDC", Qgis.Info
            )

    def loadSettingsToUI(self, dolabels=False):
        try:
            settingsUI = self.layerSettingsUI
            settingsUI.showLabelsBox.setEnabled(self.layer.haslabels)
            settingsUI.showLabelsBox.setChecked(self.settings["dolabels"])
            settingsUI.recentLabelsButton.setEnabled(self.layer.haslabels)
            settingsUI.allLabelsButton.setEnabled(self.layer.haslabels)
            settingsUI.allLabelsButton.setChecked(not self.settings["recentlabels"])
            settingsUI.labeltimeBox.setEnabled(self.layer.haslabels)
            settingsUI.labeltimeBox.setValue(
                self.settings["labeltime"] / self.labelTimeFactor
            )
            settingsUI.xLabelOffsetBox.setEnabled(self.layer.haslabels)
            settingsUI.yLabelOffsetBox.setEnabled(self.layer.haslabels)
            settingsUI.labelSizeBox.setEnabled(self.layer.haslabels)
            settingsUI.fademodeBox.setChecked(self.layer.fademode)
            settingsUI.hispeedBox.setChecked(self.layer.hispeed)
            labeloffsets = self.settings["labeloffsets"]
            settingsUI.xLabelOffsetBox.setValue(labeloffsets[0])
            settingsUI.yLabelOffsetBox.setValue(-labeloffsets[1])  # Y is inverted
            settingsUI.labelSizeBox.setValue(labeloffsets[2])
            settingsUI.endpointBox.setChecked(labeloffsets[3])

        except Exception as e:
            QgsMessageLog.logMessage(
                "Unable to recover layer settings. " + str(e), "QTDC", Qgis.Info
            )
            pass

    def saveSettings(self):

        # QgsMessageLog.logMessage("Saving settings "+str(self.timeshiftvalue),"QTDC", Qgis.Info)
        if "timeshiftsetting" in self.settings:
            del self.settings["timeshiftsetting"]
        textsettings = json.dumps(self.settings)
        if self.s:
            try:
                self.s.setValue("QgisTDC/layer_settings", textsettings)
                QgsMessageLog.logMessage("SAVE settings.", "QTDC", Qgis.Info)
            except:
                QgsMessageLog.logMessage(
                    "Unable to save layer settings.", "QTDC", Qgis.Info
                )
                pass

    def getsettings(self):
        QgsMessageLog.logMessage(str(self.settings), "QTDC", Qgis.Info)
        return self.settings

    def editsettings(self):
        QgsMessageLog.logMessage("EDIT settings.", "QTDC", Qgis.Info)
        self.loadSettingsToUI()
        self.settingsDialog.show()
        result = self.settingsDialog.exec_()
        if result == QDialog.Accepted:
            self.settings["dolabels"] = (
                self.layer.haslabels and self.layerSettingsUI.showLabelsBox.isChecked()
            )
            self.settings["hispeed"] = self.layerSettingsUI.hispeedBox.isChecked()
            self.settings[
                "recentlabels"
            ] = self.layerSettingsUI.recentLabelsButton.isChecked()
            self.settings["labeltime"] = (
                self.layerSettingsUI.labeltimeBox.value() * self.labelTimeFactor
            )
            self.settings["fademode"] = self.layerSettingsUI.fademodeBox.isChecked()
            xoff = self.layerSettingsUI.xLabelOffsetBox.value()
            yoff = 0 - self.layerSettingsUI.yLabelOffsetBox.value()  # invert y offset
            self.settings["labeloffsets"] = [
                xoff,
                yoff,
                self.layerSettingsUI.labelSizeBox.value(),
                self.layerSettingsUI.endpointBox.isChecked(),
            ]
            self.saveSettings()

        else:
            return None
        return self.settings

    def setrenderspeed(self, hispeed):
        self.hispeed = hispeed
        if self.hispeed:
            if self.messageBar:
                self.messageBar.pushMessage(
                    "Cached rendering has been activated.  EXPECT DELAYS with map redraw/resizing events.",
                    level=Qgis.Info,
                    duration=5,
                )
            self.refreshed()
            QgsApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            QgsMessageLog.logMessage("Render speed set to HIGH.", "QTDC", Qgis.Info)
        else:
            QgsMessageLog.logMessage("Render speed set to LOW.", "QTDC", Qgis.Info)

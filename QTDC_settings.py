#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import os
from pathlib import Path

from PyQt5 import uic

# from PyQt5 import QtWidgets

from qgis.PyQt import QtGui, QtCore
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *

from qgis.PyQt import QtGui, QtCore, QtWidgets
from qgis.gui import QgsFileWidget
from qgis.core import Qgis, QgsMessageLog


FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "QTDCsettings.ui")
)

# Simple dialog for specifying a time value


class QTDCsettingsDialog(QtWidgets.QDialog, FORM_CLASS):

    settingsPath = "QgisTDC/TDCsettings/"

    # Default settings

    # Map canvas text
    showText = True
    textSize = 10
    textColor = QColor(200, 200, 0, 150)

    def __init__(self, mbar, parent=None):
        """Constructor."""
        super(QTDCsettingsDialog, self).__init__(parent)

        self.setupUi(self)
        self.setModal(True)
        self.captureFolderChooser.setStorageMode(QgsFileWidget.GetDirectory)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.messageBar = mbar
        # Map Capture defaults
        self.captureFolder = os.path.abspath(Path.home())  # Initialize to home folder
        self.captureFolderChooser.setFilePath(self.captureFolder)
        self.captureFilePrefix = "Image_"
        self.readSettings()

    def readSettings(self):
        settings = QSettings()
        try:
            sizeValue = settings.value(self.settingsPath + "mapTextSize")
            if not sizeValue == None:
                self.textSize = int(sizeValue)
            self.textSizeSpinner.setValue(self.textSize)
            c = self.loadColor()
            if not (c == None):
                self.textColor = c
            self.textColorButton.setColor(self.textColor)
            folderValue = settings.value(self.settingsPath + "captureFolder")
            if not (folderValue == None):
                self.captureFolder = folderValue
            prefixValue = settings.value(self.settingsPath + "captureFilePrefix")
            if not (prefixValue == None):
                self.captureFilePrefix = prefixValue
            self.captureFolderChooser.setFilePath(self.captureFolder)
            self.capturePrefixText.setText(self.captureFilePrefix)
        except:
            self.messageBar.pushMessage(
                "Failed to initialize all settings.", level=Qgis.Info, duration=3
            )

    def accept(self):
        QgsMessageLog.logMessage("SAVING SETTINGS", "QTDC")
        self.textSize = self.textSizeSpinner.value()
        self.textColor = self.textColorButton.color()
        self.captureFolder = self.captureFolderChooser.filePath()
        self.captureFilePrefix = self.capturePrefixText.text()
        self.showText = self.showInfoTextBox.isChecked()
        settings = QSettings()
        settings.setValue(self.settingsPath + "mapTextSize", self.textSize)
        self.saveColor(self.textColor)
        folder = self.captureFolderChooser.filePath()
        if folder:
            settings.setValue(self.settingsPath + "captureFolder", self.captureFolder)
        prefix = self.capturePrefixText.text()
        if prefix:
            settings.setValue(self.settingsPath + "captureFilePrefix", prefix)
        self.done(QtWidgets.QDialog.Accepted)

    def saveColor(self, c):
        settings = QSettings()
        settings.setValue(self.settingsPath + "mapTextRed", c.red())
        settings.setValue(self.settingsPath + "mapTextGreen", c.green())
        settings.setValue(self.settingsPath + "mapTextBlue", c.blue())
        settings.setValue(self.settingsPath + "mapTextAlpha", c.alpha())

    def loadColor(self):
        r = b = g = a = c = None
        settings = QSettings()
        r = settings.value(self.settingsPath + "mapTextRed")
        g = settings.value(self.settingsPath + "mapTextGreen")
        b = settings.value(self.settingsPath + "mapTextBlue")
        a = settings.value(self.settingsPath + "mapTextAlpha")
        if not (r == None) and not (g == None) and not (b == None) and not (a == None):
            c = QColor(int(r), int(g), int(b), int(a))
        else:
            self.messageBar.pushMessage(
                "COLOR setting load failed.", level=Qgis.Info, duration=3
            )
        return c

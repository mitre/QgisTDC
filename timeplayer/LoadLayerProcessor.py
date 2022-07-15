#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import time
import hashlib
import os
import os.path
import sys

from qgis.PyQt import QtGui, QtCore, QtWidgets
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import QDialog, QColorDialog, QDialogButtonBox
from datetime import datetime, timezone
from dateutil.parser import parse

from qgis.core import Qgis, QgsMessageLog, QgsExpression, QgsApplication

from .LoadLayerState import LoadLayerState
from .LoadLayer import Ui_LoadLayerDialog
from .TimeDataLayer import TimeDataLayer
from .SavedSettingsDialog import Ui_savedSettingsDialog


class LoadLayerProcessor:

    # set default time and time zone for datetime parsing
    DEFAULT = parse("00:00Z")

    baseTimeMillis = (
        3124224000  # epoch seconds for 1-Jan-2069 which is 1970 as epoch seconds
    )
    # if time sample value exceeds this base value then year >= 2069 if represented as seconds
    # so assume value is time in milliseconds since epoch
    baseTimeMicros = 3124224000000  # epoch milliseconds for 1-Jan-2069.
    # If time sample value exceeds this, assume microseconds

    def __init__(self, canvas):
        super(LoadLayerProcessor, self).__init__()

        self.canvas = canvas
        # Connect to the Load Layer dialog to capture inputs from its controls (epoch field, time multiplier)
        self.loadlayerDialog = QDialog(self.canvas)
        self.loadlayerUI = Ui_LoadLayerDialog()
        self.loadlayerUI.setupUi(self.loadlayerDialog)

        self.loadlayerUI.utcoffsetBox.valueChanged.connect(self.setTimeZone)

        self.loadstate = LoadLayerState()

        self.epochname = self.loadlayerUI.timeattributeBox.currentText()

        QgsMessageLog.logMessage(
            "TIME ATTRIBUTE IS SET AS : " + self.epochname, "QTDC", Qgis.Info
        )

        self.firstfeature = None
        self.maplayer = None
        self.dolabels = None
        self.breakout = self.loadlayerUI.attributecolorCheckBox.isChecked()

        self.ssDialog = QDialog(self.canvas)
        self.saveSettingsDialog = Ui_savedSettingsDialog()
        self.saveSettingsDialog.setupUi(self.ssDialog)

    def connect(self):
        self.loadlayerUI.timeattributeBox.fieldChanged.connect(self.setepochfield)
        self.loadlayerUI.endTimeAttributeBox.fieldChanged.connect(self.setdurationfield)
        self.loadlayerUI.intervalCheckbox.stateChanged.connect(self.intervalstate)
        self.loadlayerUI.attributecolorBox.fieldChanged.connect(self.setcolorfield)
        self.loadlayerUI.labelExpressionWidget.fieldChanged.connect(self.setLabelField)
        self.loadlayerUI.attributecolorCheckBox.clicked.connect(self.setbreakout)
        self.loadlayerUI.labelCheckBox.clicked.connect(self.labelFeatures)
        self.loadlayerUI.attributeCountButton.clicked.connect(self.countfieldvalues)

    def load(self, maplayer, approved):
        self.maplayer = maplayer
        try:
            preApproved = approved
            initialfield = maplayer.fields().at(0).name()
            # get hash value from this map layer's metadata and see if we've saved
            # any settings
            settingsFile = self.lookupSettingsFile(maplayer)
            loadSettings = None
            if settingsFile != None:
                if not preApproved:
                    # If yes and not pre-approved, ask if we want to load them
                    self.saveSettingsDialog.layerNameLabel.setText(maplayer.name())
                    self.ssDialog.show()
                    loadSettings = self.ssDialog.exec_()
                else:
                    loadSettings = QDialog.Accepted
            else:
                preApproved = False

            layerfeatures = maplayer.getFeatures()
            for feature in layerfeatures:
                self.firstfeature = feature
                break

            self.loadlayerUI.timeattributeBox.setLayer(maplayer)
            self.loadlayerUI.endTimeAttributeBox.setLayer(maplayer)
            self.loadlayerUI.layerlabel.setText(maplayer.name())

            self.loadlayerUI.attributecolorBox.setLayer(maplayer)
            self.loadlayerUI.labelExpressionWidget.setLayer(maplayer)

            if loadSettings == QDialog.Accepted:
                preApproved = self.saveSettingsDialog.yesBox.isChecked() or preApproved
                # load from file
                self.loadSettingsFile(settingsFile)

                self.loadlayerUI.timeattributeBox.setField(self.loadstate.epochfield)

                self.loadlayerUI.utcoffsetBox.setValue(self.loadstate.utcOffset)
                self.loadlayerUI.selectedBox.setChecked(self.loadstate.selectedonly)

                if self.loadstate.durationfield != None:
                    self.loadlayerUI.intervalCheckbox.setChecked(True)
                    self.loadlayerUI.endTimeAttributeBox.setEnabled(True)
                else:
                    self.loadlayerUI.intervalCheckbox.setChecked(False)

                self.loadlayerUI.endTimeAttributeBox.setField(
                    self.loadstate.durationfield
                )

                if self.loadstate.colorattr != None:
                    self.loadlayerUI.attributecolorCheckBox.setChecked(True)
                    self.setbreakout(True)
                else:
                    self.loadlayerUI.attributecolorCheckBox.setChecked(False)

                self.loadlayerUI.attributecolorBox.setField(self.loadstate.colorattr)
                self.loadlayerUI.labelExpressionWidget.setExpression(
                    self.loadstate.labelExpression.expression()
                )
                if self.loadstate.labelExpression.expression() != "":
                    self.loadlayerUI.labelCheckBox.setChecked(True)
                    self.loadlayerUI.labelExpressionWidget.setEnabled(True)
                else:
                    self.loadlayerUI.labelCheckBox.setChecked(False)

                self.dolabels = self.loadlayerUI.labelCheckBox.isChecked()

            # Only connect signals here instead of __init__ to prevent interference with settings restoration above
            self.connect()

            if loadSettings != QDialog.Accepted:
                self.loadlayerUI.timeattributeBox.setField(initialfield)
                self.setepochfield(initialfield)
                self.loadlayerUI.endTimeAttributeBox.setField(initialfield)
                self.loadlayerUI.attributecolorBox.setField(initialfield)

            self.validate()

            if not preApproved:
                self.loadlayerDialog.show()
                result = self.loadlayerDialog.exec_()
            else:  # Settings are pre-approved so proceed without confirmation
                result = QDialog.Accepted

            if result == QDialog.Accepted:
                # TODO: need to add validation of Load UI entries here.
                useinterval = self.loadlayerUI.intervalCheckbox.isChecked()
                self.loadstate.selectedonly = self.loadlayerUI.selectedBox.isChecked()
                if self.breakout:
                    self.loadstate.colorattr = (
                        self.loadlayerUI.attributecolorBox.currentField()
                    )
                else:
                    self.loadstate.colorattr = None
                # Send None to TimeDataLayer for duration field if interval box is unchecked
                if not self.loadlayerUI.intervalCheckbox.isChecked():
                    self.loadstate.durationfield = None

                # Save layer settings!
                QgsMessageLog.logMessage(self.loadstate.asString(), "QTDC", Qgis.Info)
                # Write layer state file
                self.saveSettingsFile(maplayer)
                return self.loadstate, preApproved

        except:
            etype, val, trace = sys.exc_info()
            tbline = trace.tb_lineno
            QgsMessageLog.logMessage(
                "Exception in LoadLayerProcessor "
                + str(etype)
                + " at line "
                + str(tbline),
                "QTDC",
                Qgis.Warning,
            )
        return None, False

    def setTimeZone(self):
        self.loadstate.utcOffset = self.loadlayerUI.utcoffsetBox.value()
        self.validate()

    def intervalstate(self, state):
        self.loadlayerUI.endTimeAttributeBox.setEnabled(
            self.loadlayerUI.intervalCheckbox.isChecked()
        )
        self.validate()

    def labelFeatures(self, l):
        self.dolabels = self.loadlayerUI.labelCheckBox.isChecked()
        self.loadlayerUI.labelExpressionWidget.setEnabled(self.dolabels)
        self.loadstate.labelExpression = None
        self.validate()

    def setLabelField(self, lf=None, val=None):
        self.loadstate.labelExpression = None
        expressionText = self.loadlayerUI.labelExpressionWidget.currentText()
        if self.loadlayerUI.labelExpressionWidget.isExpression():
            self.loadstate.labelExpression = QgsExpression(expressionText)
        else:
            self.loadstate.labelExpression = QgsExpression(expressionText + "\n")
        self.validate()

    def setbreakout(self, bo):
        self.breakout = bo
        self.loadlayerUI.attributecolorBox.setEnabled(bo)
        self.loadlayerUI.attributeCountButton.setEnabled(bo)
        if bo:
            self.setcolorfield(self.loadlayerUI.attributecolorBox.currentField())
        self.validate()

    def setcolorfield(self, cf):
        if self.breakout:
            self.colorfield = cf

    def countfieldvalues(self):
        if self.loadlayerUI.attributecolorCheckBox.isChecked():
            # fldidx = self.maplayer.fields().indexFromName(self.loadstate.colorattr)
            # Get the index from the UI instead of loadstate.  There are situations where loadstate hasn't
            # been committed because this event occurs before the load dialog is confirmed by user.
            fldidx = self.maplayer.fields().indexFromName(
                self.loadlayerUI.attributecolorBox.currentField()
            )
            values = self.maplayer.uniqueValues(fldidx)
            self.loadlayerUI.attributecountLabel.setText(
                str(len(values))
                + " values in "
                + self.loadlayerUI.attributecolorBox.currentField()
            )

    def setepochfield(self, ef):
        self.loadstate.epochfield = ef
        self.epochname = self.loadlayerUI.timeattributeBox.currentField()
        self.validate()
        self.parsetimesample(self.epochname)

    def setdurationfield(self, df):
        self.loadstate.durationfield = df
        self.durationname = self.loadlayerUI.endTimeAttributeBox.currentField()
        self.validate()
        self.parsetimesample(self.durationname)

    def validate(self):
        timefield = self.loadlayerUI.timeattributeBox.currentField()
        durationfield = self.loadlayerUI.endTimeAttributeBox.currentField()
        durationok, labelsok, epochok = False, False, False
        labelsok = not self.dolabels
        if self.dolabels:
            labelsok = self.loadlayerUI.labelExpressionWidget.isValidExpression()
        if timefield:
            epochok = self.parsetimesample(timefield)
        if self.loadlayerUI.intervalCheckbox.isChecked():
            if durationfield:
                durationok = self.parsetimesample(durationfield)
            QgsMessageLog.logMessage(
                "epochok: "
                + str(epochok)
                + " durationok:"
                + str(durationok)
                + " labelsok:"
                + str(labelsok),
                "QTDC",
                Qgis.Info,
            )
            self.setcontinue(epochok and durationok and labelsok)
        else:
            QgsMessageLog.logMessage(
                "epochok: " + str(epochok) + " labelsok:" + str(labelsok),
                "QTDC",
                Qgis.Info,
            )
            self.setcontinue(epochok and labelsok)

    def testDateManual(self, s):
        ds = s
        QgsMessageLog.logMessage(ds, "QTDC", Qgis.Info)
        dsl = ds.split(".")
        QgsMessageLog.logMessage("Test manual..." + ds, "QTDC", Qgis.Info)
        QgsMessageLog.logMessage(ds[:4], "QTDC", Qgis.Info)
        QgsMessageLog.logMessage(ds[5:7], "QTDC", Qgis.Info)
        QgsMessageLog.logMessage(ds[8:10], "QTDC", Qgis.Info)
        QgsMessageLog.logMessage(ds[11:13], "QTDC", Qgis.Info)
        QgsMessageLog.logMessage(ds[14:16], "QTDC", Qgis.Info)
        QgsMessageLog.logMessage(ds[17:19], "QTDC", Qgis.Info)
        if len(dsl) > 1:
            QgsMessageLog.logMessage(ds[20:], "QTDC", Qgis.Info)
            dtod = datetime(
                int(ds[:4]),
                int(ds[5:7]),
                int(ds[8:10]),
                int(ds[11:13]),
                int(ds[14:16]),
                int(ds[17:19]),
                int(ds[20:]),
            )
        else:
            dtod = datetime(
                int(ds[:4]),
                int(ds[5:7]),
                int(ds[8:10]),
                int(ds[11:13]),
                int(ds[14:16]),
                int(ds[17:19]),
            )

    def extractSample(self, s):
        if s is None:
            return None

        if isinstance(s, (int, float)):
            value = s
        else:
            if isinstance(s, str) and len(s) == 0:
                return None
            try:
                value = float(s)
            except:
                # not a number - try as datetime string format
                try:
                    if isinstance(s, str):
                        self.loadlayerUI.utcoffsetBox.setEnabled(True)
                        self.loadstate.utcOffset = self.loadlayerUI.utcoffsetBox.value()
                        try:
                            QgsMessageLog.logMessage(
                                "Calling testdate...", "QTDC", Qgis.Info
                            )
                            self.testDateManual(s)
                            QgsMessageLog.logMessage(
                                "MANUAL date parse.", "QTDC", Qgis.Info
                            )
                            return Manual()
                        except:
                            try:
                                QgsMessageLog.logMessage(
                                    de.message(), "QTDC", Qgis.Info
                                )
                                d = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                                QgsMessageLog.logMessage(
                                    "StrpTime date parser.", "QTDC", Qgis.Info
                                )
                                return StrpTime()
                            except:
                                QgsMessageLog.logMessage(
                                    "Using generic date string parser.",
                                    "QTDC",
                                    Qgis.Info,
                                )
                                parse(
                                    s,
                                    dayfirst=False,
                                    default=LoadLayerProcessor.DEFAULT,
                                )
                                return DateString()

                    else:
                        QgsMessageLog.logMessage(
                            "Non-string time attribute. UTC assumed.", "QTDC", Qgis.Info
                        )
                        if isinstance(s, QDateTime):
                            QgsMessageLog.logMessage(
                                "DATETIME attribute.", "QTDC", Qgis.Info
                            )
                            return DateTimeParser()
                        elif isinstance(s, QDate):
                            QgsMessageLog.logMessage(
                                "DATE attribute.", "QTDC", Qgis.Info
                            )
                            return DateParser()
                        s = str(s)

                    QgsMessageLog.logMessage(
                        "Attempting generic parser.", "QTDC", Qgis.Info
                    )
                    parse(s, dayfirst=False, default=LoadLayerProcessor.DEFAULT)
                    return DateString()
                except:
                    # value not convertable to string or not parsable as a datetime format
                    QgsMessageLog.logMessage(
                        "Failed to parse epoch field.", "QTDC", Qgis.Info
                    )
                    return None

        QgsMessageLog.logMessage("Numeric time attribute.", "QTDC", Qgis.Info)
        self.loadstate.utcOffset = 0
        self.loadlayerUI.utcoffsetBox.setEnabled(
            False
        )  # Only allow utc offset for strings
        if value > LoadLayerProcessor.baseTimeMicros:
            # if value is > than epoch milliseconds year 2069, treat it as microseconds
            self.multiplier = 100000.0
            return Epoch_uSec()
        elif value > LoadLayerProcessor.baseTimeMillis:
            # if treat this value as seconds since epoch then year >= 2069
            # so assume value is time in milliseconds not seconds since epoch.
            # convert milliseconds since 1-Jan-1970 epoch to seconds
            self.multiplier = 1000.0
            return EpochMSec()
        else:
            # seconds since 1-Jan-1970 epoch
            self.multiplier = 1.0
            return EpochSec()

    def parsetimesample(self, fieldname):
        if self.firstfeature:
            self.loadlayerUI.fieldLabel.setText(fieldname)
            epochvalue = self.firstfeature[fieldname]

            # Prepare a text sample from QDateTime API if value is QDateTime (UTC assumed)
            if isinstance(epochvalue, QDateTime):
                epochsample = epochvalue.toString("yyyy-MM-dd hh:mm:ss.z")
                epochsample = epochsample + " " + epochvalue.timeZone().comment()
            elif isinstance(epochvalue, QDate):
                epochsample = epochvalue.toString("yyyy-MM-dd")
            else:
                epochsample = epochvalue

            QgsMessageLog.logMessage(
                "sample EPOCHVALUE: " + str(epochsample), "QTDC", Qgis.Info
            )
            self.loadlayerUI.timesampleText.setText(str(epochsample))
            self.loadlayerUI.parsedvalueText.setText(" ")
            try:
                timestring = ""
                dateFmt = self.extractSample(epochvalue)
                if not dateFmt is None:
                    self.loadstate.dateFormatter = dateFmt
                    secs = dateFmt.parseDate(epochvalue)
                    if secs is None:
                        timestring = "Failed to parse timestamp"
                    else:
                        secs = secs + (self.loadstate.utcOffset * 3600)
                        timestring = time.strftime(
                            "%Y-%m-%d %H:%M:%S", time.gmtime(int(secs))
                        )
                else:
                    QgsMessageLog.logMessage(
                        "Failed to get date parser.", "QTDC", Qgis.Info
                    )
                    return False
                self.loadlayerUI.fieldLabel.setText(fieldname)
            except Exception as e:
                timestring = str(e)
                return False
            self.loadlayerUI.parsedvalueText.setText(timestring)
            return True
        return False

    def setcontinue(self, cont):
        QgsMessageLog.logMessage("SetContinue: " + str(cont), "QTDC", Qgis.Info)
        self.loadlayerUI.buttonBox.button(QDialogButtonBox.Ok).setEnabled(cont)

    def loadSettingsFile(self, path):
        file = os.path.join(path, "settings.json")
        json = ""
        with open(file, "r") as f:
            json = f.read()
            QgsMessageLog.logMessage("READING IN JSON FILE", "QTDC", Qgis.Info)
            QgsMessageLog.logMessage(json, "QTDC", Qgis.Info)
            f.close()

        self.loadstate.loadJson(json)

    def saveSettingsFile(self, maplayer):
        hashValue = self.getMapLayerHash(maplayer)
        path = os.path.join(QgsApplication.qgisSettingsDirPath(), ".QTDC", hashValue)
        # if path doesn't exist, make it
        if not os.path.exists(path):
            os.makedirs(path)

        file = os.path.join(path, "settings.json")
        QgsMessageLog.logMessage(file, "QTDC", Qgis.Info)
        with open(file, "w") as f:
            f.write(self.loadstate.asJson())
            f.close()

    def lookupSettingsFile(self, maplayer):
        hashValue = self.getMapLayerHash(maplayer)
        QgsMessageLog.logMessage("Hash Value: " + hashValue, "QTDC", Qgis.Info)
        QgsMessageLog.logMessage(
            QgsApplication.qgisSettingsDirPath(), "QTDC", Qgis.Info
        )
        path = os.path.join(QgsApplication.qgisSettingsDirPath(), ".QTDC", hashValue)
        if os.path.exists(path):
            return path

        return None

    def getMapLayerHash(self, maplayer):
        m = hashlib.sha256()
        m.update(maplayer.name().encode())
        m.update(str(len(maplayer.fields())).encode())
        m.update(str(maplayer.featureCount()).encode())
        return m.hexdigest()


##################################################


class DateString:
    """
    Simple wrapper to dateutil.parser to parse string and return timestamp
    Returns number of seconds since epoch as float

    Raises:
     ValueError	Raised for invalid or unknown string format, if the provided tzinfo is not in a valid format,
                    or if an invalid date would be created.
     OverflowError	Raised if the parsed date exceeds the largest valid C integer on your system.
    """

    def parseDate(self, s):
        return parse(s, dayfirst=False, default=LoadLayerProcessor.DEFAULT).timestamp()


##


class StrpTime:
    def parseDate(self, s):
        try:
            d = datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
        except:
            d = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return d.timestamp()


class IsoFormat:
    def parseDate(self, s):
        return (
            datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )


##


class Manual:
    def parseDate(self, s):
        ds = s
        dsl = ds.split(".")
        if len(dsl) > 1:
            if len(dsl[1]) < 6:
                dtod = datetime(
                    int(ds[:4]),
                    int(ds[5:7]),
                    int(ds[8:10]),
                    int(ds[11:13]),
                    int(ds[14:16]),
                    int(ds[17:19]),
                    int(ds[20:]),
                    tzinfo=timezone.utc,
                )
            else:
                dtod = datetime(
                    int(ds[:4]),
                    int(ds[5:7]),
                    int(ds[8:10]),
                    int(ds[11:13]),
                    int(ds[14:16]),
                    int(ds[17:19]),
                    int(ds[20:26]),
                    tzinfo=timezone.utc,
                )

        else:
            dtod = datetime(
                int(ds[:4]),
                int(ds[5:7]),
                int(ds[8:10]),
                int(ds[11:13]),
                int(ds[14:16]),
                int(ds[17:19]),
                tzinfo=timezone.utc,
            )
        return dtod.timestamp()


class EpochSec:
    """
    Converts value as seconds since epoch to float.

    Raises:
     ValueError	Raised for invalid value that cannot be converted to float.
    """

    # parse time as epoch seconds
    def parseDate(self, s):
        return float(s)


##
class DateTimeParser:
    def parseDate(self, d):
        d.setTimeZone(QTimeZone.utc())
        return d.toSecsSinceEpoch()


##
class DateParser:
    def parseDate(self, d):
        dt = QDateTime(d, QTime(), QTimeZone.utc())
        return dt.toSecsSinceEpoch()


class EpochMSec:
    """
    Converts value as milliseconds since epoch to float
    and returns value as seconds.

    Raises:
     ValueError	Raised for invalid value that cannot be converted to float.
    """

    def parseDate(self, s):
        return float(s) / 1000


class Epoch_uSec:
    """
    Converts value as microseconds since epoch to float
    and returns value as seconds.

    Raises:
     ValueError	Raised for invalid value that cannot be converted to float.
    """

    def parseDate(self, s):
        return float(s) / 1000000


##################################################

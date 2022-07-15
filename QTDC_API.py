#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2022 The MITRE Corporation
#

from qgis.core import QgsApplication, Qgis, QgsMessageLog, QgsExpression

from qgis.PyQt.QtCore import QDate, QDateTime

from dateutil.parser import parse

from .timeplayer.TimeDataLayer import TimeDataLayer
from .timeplayer.LoadLayerTask import LoadLayerTask
from .timeplayer.LoadLayerState import LoadLayerState
from .timeplayer.LoadLayerProcessor import (
    LoadLayerProcessor,
    DateString,
    StrpTime,
    IsoFormat,
    Manual,
    EpochSec,
    DateTimeParser,
    DateParser,
    EpochMSec,
)


class QTDC_API:
    """
    This is an API wrapper class to provide other plugins limited access to QTDC core capabilities.

    This API was an after thought and was added late in the development of QTDC.
    """

    def __init__(self, qtdc):
        # Construct the QTDC api
        #
        # Parameters:
        #   qtdc (QgisTDC_dockwidget): The QTDC plugin being controlled by this API
        #
        # Returns:
        #   api (QTDC_API)           : A reference to this API
        #

        self.qtdc = qtdc

        # Get handles for the timeline, timeplayer and load finisher objects
        self.loadfinisher = qtdc.completeLoading
        self.timeplayer = qtdc.timeplayer
        self.timeline = qtdc.timeline

    def display(self, show=True):
        # display(show): Show or hide the QTDC UI
        #
        # Parameters:
        #   show (bool): True specifies show;  False specifies hide
        #

        if show:
            self.qtdc.show()
        else:
            self.qtdc.hide()

    def loadLayer(self, maplayer, timeattr, interval=None, color=None, labelexpr=None):
        # loadLayer(maplayer, timeattr, interval, color, labelexpr):
        #       Load a map layer in QTDC as a time data layer
        #
        # Parameters:
        #   maplayer (QgsVectorLayer)   : The map layer to load
        #   timeattr (string)           : The attribute for time (or start time)
        #   interval (string)           : Optional: End time attribute
        #   color (string)              : Optional: The attribute for 'color by attribute' rendering
        #   labelexpr (string)          : Optional: The expression to use for generating label text
        #
        # Returns:
        #   layeruid (uuid)           : String version of the UUID for the loaded layer. Returns None if firstfeature not found.
        #

        QgsMessageLog.logMessage("***API***  Begin loadLayer...", "QTDC", Qgis.Info)
        #
        # Prepare the load state for the layer from the parameters
        loadstate = LoadLayerState()
        loadstate.epochfield = timeattr
        loadstate.durationfield = interval
        loadstate.colorattr = color
        if labelexpr is not None:
            loadstate.labelExpression = QgsExpression(labelexpr)

        # Get a sample value for finding a date parser
        layerfeatures = maplayer.getFeatures()
        firstfeature = None
        for feature in layerfeatures:
            firstfeature = feature
            break
        if firstfeature:
            timesample = firstfeature[timeattr]
            QgsMessageLog.logMessage(
                "***API***  Time sample class is:  " + timesample.__class__.__name__,
                "QTDC",
                Qgis.Info,
            )
            dateFmt = self.getDateParser(timesample)
            if not dateFmt is None:
                loadstate.dateFormatter = dateFmt
                QgsMessageLog.logMessage(
                    "***API***    Loadstate dateformatter set.  "
                    + str(dateFmt.parseDate(timesample)),
                    "QTDC",
                    Qgis.Info,
                )

            QgsMessageLog.logMessage(
                "***API***  EPOCH..." + str(loadstate.epochfield), "QTDC", Qgis.Info
            )
            QgsMessageLog.logMessage(
                "***API***  DURATION..." + str(loadstate.durationfield),
                "QTDC",
                Qgis.Info,
            )
            QgsMessageLog.logMessage(
                "***API***  COLOR..." + str(loadstate.colorattr), "QTDC", Qgis.Info
            )
            QgsMessageLog.logMessage(
                "***API***  EXPRESSION..." + str(loadstate.labelExpression),
                "QTDC",
                Qgis.Info,
            )

            # Make the timedatalayer and connect the necessary callbacks for re-loading
            timedatalayer = TimeDataLayer(self.timeplayer.canvas, maplayer, loadstate)
            timedatalayer.layerUpdate.connect(self.timeplayer.updated)
            timedatalayer.layerReload.connect(self.timeplayer.reloadmaplayer)

            # Spawn a task to perform the actual loading of data into the layer. The timeplayer.loadingComplete method is called when done.
            self.timeplayer.loadfinisher = self.qtdc.completeLoading
            loader = LoadLayerTask(
                "Loading " + maplayer.name(),
                maplayer,
                timedatalayer,
                self.timeplayer.loadingComplete,
            )
            QgsApplication.taskManager().addTask(loader)

            # Return the layer's uid
            return timedatalayer.uid
        else:
            return None

    def reloadLayer(self, uid):
        # reloadLayer(uid):  Request a reload for a timedatalayer in QTDC
        #
        # Parameters:
        #   uid (uuid)    : The uid that was created for the layer when it was loaded
        #

        # Get the timedata layer for the provided uid
        timedatalayer = self.timeplayer.getLayer(uid)

        # Request a reload on the layer if one was returned
        if timedatalayer:
            timedatalayer.requestReload()
            timedatalayer.update()

    def pushData(self, uid, datalist):
        # pushData(uid, datalist):  Push features directly into QTDC layer
        #
        # Parameters:
        #   uid (uuid)      : The uid of the layer to receive the new features.
        #   datalist (list) : List containing the new features
        #

        # Get the timedata layer for the provided uid
        timedatalayer = self.timeplayer.getLayer(uid)

        # Push the new data to the layer if one was returned
        if timedatalayer:
            timedatalayer.updateLayer(datalist)
            timedatalayer.layerUpdate.emit(timedatalayer)
        else:
            QgsMessageLog.logMessage(
                "API*** - Layer with uid: " + str(uid) + " not found.",
                "QTDC",
                Qgis.Info,
            )

    def isLayerLoaded(self, uid):
        # isLayerLoaded(uid):  Check if a layer is loaded in QTDC
        #
        # Parameters:
        #   uid (uuid)    : The uid that was created for the layer when it was loaded
        #
        # Returns:
        #   status (bool)   : True indicates layer is loaded; False indicates layer is not loaded.
        #

        # Get the layer for the provided uid and return True if it was found, False if not
        timedatalayer = self.timeplayer.getLayer(uid)
        return timedatalayer is not None

    def play(self):
        # play():  Start QTDC animation
        #
        if not self.timeplayer.isAnimating():
            self.timeplayer.animate()  # Start animation if stopped

    def pause(self):
        # pause():  Pause QTDC animation
        if self.timeplayer.isAnimating():
            self.timeplayer.setpause(True)  # False un-pauses animation

    def setTime(self, t):
        # setTime(t):  Set the data time of the QTDC time window leading edge
        #
        # Parameters:
        #   t (double)  : epoch seconds time for the desired data time for the timeline
        #

        self.pause()
        # Get the current time window history and use it with the new time to set the time window time
        history = self.timeplayer.gethistory()
        self.qtdc.adjusthistory(history)
        self.qtdc.settime(t, history)
        self.timeplayer.showdata(t)

    def getTime(self):
        # getTime():  Get the current data time (leading edge) of the QTDC time window
        #
        # Returns:
        #   t (double): epoch seconds time of time window
        #

        dataTime = self.timeplayer.currentTime
        return dataTime

    def closeLayer(self, uid):
        # closeLayer(uuid):  Close a timeline layer
        #
        # Parameters:
        #   uid (uuid):  The uid that was created for the layer when it was loaded
        #

        QgsMessageLog.logMessage(
            "***API***  Requesting layer close " + str(uid), "QTDC", Qgis.Info
        )
        timedatalayer = self.timeplayer.getLayer(uid)

        timedatalayer = self.timeplayer.getLayer(uid)
        if timedatalayer is not None:
            timedatalayer.requestClose()

    def closeAllLayers(self):
        # closeAllLayers():  Close all timeline layers
        #

        # Make a local layer reference set because closing layers modifies the timeplayer.layers structure
        #
        layerRefs = []
        for l in self.timeplayer.layers:
            layerRefs.append(l)

        # Close each layer
        for l in layerRefs:
            l.requestClose()

    def getVisibleDataIds(self, uid):
        # getVisibleDataIds(uuid):  Get a list of feature Ids for features that are within the QTDC data window for the layer with uid
        #
        # Parameters:
        #   uid (uuid):  The uid that was created for the layer when it was loaded
        #
        # Returns:
        #   fids (list) : list of feature ids
        #

        timedatalayer = self.timeplayer.getLayer(uid)
        fids = []
        if timedatalayer is not None:
            fids = timedatalayer.getWindowDataIds()
        return fids

    def getTimeWindow(self):
        # getTimeWindow():  Get the min and max times of the timeline time window.
        #
        # Returns:
        #   mintime (double): epoch seconds of time window minimum time
        #   maxtime (double): epoch seconds of time window maximum time
        #

        maxtime = self.timeline.barwidget.time
        mintime = maxtime - self.timeline.barwidget.history
        return mintime, maxtime

    def connectTimeSignal(self, socket):
        # connectTimeSignal(socket):  Connect a socket to the signal emitted for QTDC time set events
        #
        # Parameters:
        #   socket:  The socket method that will execute when the time signal is emitted
        #

        self.qtdc.setTimeSignal.connect(socket)

    # *************************************************
    # Date parser used to determine how the selected time fields should be parsed
    #
    # Parameters:
    #   s (variant) : Sample time value to parse
    #
    # Returns:
    #   parser (object) : Parser method for parsing date values
    #
    def getDateParser(self, s):
        QgsMessageLog.logMessage(
            "***API***  Finding date parser for: " + str(s), "QTDC", Qgis.Info
        )
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
                        try:
                            QgsMessageLog.logMessage(
                                "***API***  Calling testdate...", "QTDC", Qgis.Info
                            )
                            self.testDateManual(s)
                            QgsMessageLog.logMessage(
                                "***API***  MANUAL date parse.", "QTDC", Qgis.Info
                            )
                            return Manual()
                        except:
                            try:
                                QgsMessageLog.logMessage(
                                    de.message(), "QTDC", Qgis.Info
                                )
                                d = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                                QgsMessageLog.logMessage(
                                    "***API***  StrpTime date parser.",
                                    "QTDC",
                                    Qgis.Info,
                                )
                                return StrpTime()
                            except:
                                QgsMessageLog.logMessage(
                                    "***API***  Using generic date string parser.",
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
                            "***API***  Non-string time attribute. UTC assumed.  "
                            + s.__class__.__name__,
                            "QTDC",
                            Qgis.Info,
                        )
                        if isinstance(s, QDateTime):
                            QgsMessageLog.logMessage(
                                "***API***  DATETIME attribute.", "QTDC", Qgis.Info
                            )
                            return DateTimeParser()
                        elif isinstance(s, QDate):
                            QgsMessageLog.logMessage(
                                "***API***  DATE attribute.", "QTDC", Qgis.Info
                            )
                            return DateParser()
                        else:
                            QgsMessageLog.logMessage(
                                "***API***  Unable to determine correct DateTime parser.  "
                                + s.__class__.__name__,
                                "QTDC",
                                Qgis.Info,
                            )
                        s = str(s)
                    QgsMessageLog.logMessage(
                        "***API***  Attempting generic parser.", "QTDC", Qgis.Info
                    )
                    parse(s, dayfirst=False, default=LoadLayerProcessor.DEFAULT)
                    return DateString()
                except:
                    # value not convertable to string or not parsable as a datetime format
                    QgsMessageLog.logMessage(
                        "***API***  Failed to parse epoch field.", "QTDC", Qgis.Warning
                    )
                    return None

        QgsMessageLog.logMessage(
            "***API***  Numeric time attribute.", "QTDC", Qgis.Info
        )
        if value > LoadLayerProcessor.baseTimeMillis:
            # if treat this value as seconds since epoch then year >= 2069
            # so assume value is time in milliseconds not seconds since epoch.
            # convert milliseconds since 1-Jan-1970 epoch to seconds
            self.multiplier = 1000.0
            return EpochMSec()
        else:
            # seconds since 1-Jan-1970 epoch
            self.multiplier = 1.0
            return EpochSec()

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

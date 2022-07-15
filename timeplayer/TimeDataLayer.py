#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import sys
import time
import numpy as np
import uuid

from datetime import datetime
from qgis.PyQt import QtCore
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import QDialog

from PyQt5.QtCore import pyqtSignal

from qgis.gui import QgsMapCanvasItem
from qgis.core import (
    Qgis,
    QgsRectangle,
    QgsMessageLog,
    QgsWkbTypes,
    QgsExpressionContext,
    QgsExpressionContextScope,
    QgsProject,
    QgsCoordinateTransform,
    QgsApplication,
    QgsTask,
    QgsDateTimeFieldFormatter,
)

from .TimeDataPoint import TimeDataPoint
from .TimeDataLine import TimeDataLine
from .TimeDataPolygon import TimeDataPolygon

from .LayerSettings import Ui_LayerSettingsDialog
from .LayerSettingsEditor import LayerSettingsEditor
from .LayerMarkers import LayerMarkers
from .LayerMarkerObject import markerObject
from .GeometryTypes import geometryTypes
from .DecoratorArgs import decoratorArgs


class TimeDataLayer(QgsMapCanvasItem):
    """A container for renderable time data elements"""

    #
    # This class implements a layer of time data elements as a QgsMapCanvasItem for rendering.
    # The data is contained in an array and sorted by time. A parallel time index array
    # is also maintained for rapid indexing by time window limits (start, end times). The times
    # are stored internally as float seconds to overcome an issue with the animation framework
    # when milliseconds are used, by which values are internally truncated during animation.
    # The data is also indexed by a chunk array to expedite random access.
    #

    # TODO:  Combine these makeshift signal classes, or better yet, use pyqtSignal instead
    class LayerUpdate(QObject):
        # This is a makeshift signal that can be emitted to indicate the
        # completion of an update to this layer's data
        def __init__(self):
            super(TimeDataLayer.LayerUpdate, self).__init__()
            self.updateCallbacks = []
            self.updateCallbacks.append(self.noop)

        def noop(self, tdl):
            pass

        def connect(self, callback):
            self.updateCallbacks.append(callback)

        def emit(self, caller):
            for callback in self.updateCallbacks:
                callback(caller)

    class NeedsReload(QObject):
        # This is a makeshift signal that can be emitted to request reloading this layer's data
        def __init__(self):
            super(TimeDataLayer.NeedsReload, self).__init__()
            self.reloadCallbacks = []
            self.reloadCallbacks.append(self.noop)

        def noop(self, tdl):
            pass

        def connect(self, callback):
            self.reloadCallbacks.append(callback)

        def emit(self, caller):
            for callback in self.reloadCallbacks:
                callback(caller)

    class CloseRequest(QObject):
        # This is a makeshift signal that can be emitted to request closing this layer
        def __init__(self):
            super(TimeDataLayer.CloseRequest, self).__init__()
            self.callbacks = []
            self.callbacks.append(self.noop)

        def noop(self):
            pass

        def connect(self, callback):
            self.callbacks.append(callback)

        def disconnect(self, callback):
            self.callbacks.remove(callback)

        def emit(self, caller):
            for callback in self.callbacks:
                callback()

    def __init__(self, canvas, maplayer, loadstate):
        QgsMapCanvasItem.__init__(self, canvas)

        self.layerUpdate = TimeDataLayer.LayerUpdate()
        self.layerReload = TimeDataLayer.NeedsReload()
        self.layerClose = TimeDataLayer.CloseRequest()

        self.canvas = canvas
        self.maplayer = maplayer

        self.loadstate = loadstate

        self.uid = uuid.uuid4()

        self.setup(loadstate)

    def setup(self, loadstate):
        self.canvas.extentsChanged.connect(self.refreshed)

        self.layerSettingsDialog = QDialog(self.canvas)
        self.layerSettingsUI = Ui_LayerSettingsDialog()
        self.layerSettingsUI.setupUi(self.layerSettingsDialog)

        self.wkbType = self.maplayer.wkbType()
        self.maplayer.committedFeaturesAdded.connect(self.newFeatures)
        # self.maplayer.dataProvider().dataChanged.connect(self.requestReload)

        self.initialfilter = self.maplayer.subsetString()
        mapextent = self.canvas.extent()
        self.setRect(mapextent)

        self.resetData()

        self.starttime = 0  # Time of data window beginning
        self.ctime = 0  # Time of data window end
        self.history = 60  # Length of data window
        self.fwd = True  # Animation direction: True = forward; False = reverse
        self.startindex = 0  # Index of first element in data window
        self.endindex = 0  # Index of last element in data window
        self.incr = 1  # Increment for traversing display data, determines draw order
        self.success = False
        self.timeshift = (
            0  # Amount of time data is shifted on the timeline (defined by user)
        )

        self.loadStatusMessage = None

        # Prepare the transforms: 'transform' for transforming to canvas;
        #                        'coordinateTransform' for transforming geometries to correct CRS
        self.transform = self.canvas.transform()
        self.coordinateTransform = None

        # Make sure the layer's CRS is the same as the project.
        # If not, prepare the coordinateTransform object
        self.sourceCRS = self.maplayer.sourceCrs()
        projectCRS = QgsProject.instance().crs()

        # Connect the 'crsChanged' signal to the setCRSTransform method
        QgsProject.instance().crsChanged.connect(self.setCRSTransform)
        self.transformTask = None
        if self.sourceCRS == projectCRS:
            QgsMessageLog.logMessage(
                "Layer CRS matches project CRS.", "QTDC", Qgis.Info
            )
        else:
            QgsMessageLog.logMessage(
                "Layer CRS DOES NOT match project CRS.", "QTDC", Qgis.Info
            )
            self.coordinateTransform = QgsCoordinateTransform(
                self.sourceCRS, projectCRS, QgsProject.instance()
            )
            self.sourceCRS = projectCRS

        self.epochfield = loadstate.epochfield
        self.durationfield = loadstate.durationfield

        self.useduration = False
        self.dateFormatter = loadstate.dateFormatter
        self.colorattr = loadstate.colorattr

        # Internal value must be seconds, load state setting is stored as hours
        self.utcOffset = loadstate.utcOffset * 3600

        self.pen = QPen(Qt.yellow)
        self.pen.setWidth(3)

        self.marker = None
        self.randomized = not self.colorattr == None
        self.categorized = False
        self.markers = []
        self.attrdict = {}
        self.basealpha = 1.0
        self.paintxform = None
        self.catattr = ""
        self.isVisible = True
        self.visibleReturn = self.isVisible

        self.isLoading = False
        self.reLoadable = False
        self.loadBanner = "Loading..."

        self.hispeed = False
        self.messageBar = None
        self.dolabels = False
        self.haslabels = False
        if loadstate.labelExpression:
            self.dolabels = (
                loadstate.labelExpression.isValid()
            )  # This object is a QgsExpression
            self.haslabels = (
                loadstate.labelExpression.isValid()
            )  # Used by LayerSettingsEditor
        self.recentlabels = True
        self.labeltime = 10.0
        # self.labeloffsets = [10, 10, 10, False]
        self.decoArgs = decoratorArgs()
        self.fademode = True
        self.settingsEditor = LayerSettingsEditor(
            self.canvas, self, self.haslabels, self.isLineLayer()
        )
        QgsMessageLog.logMessage(
            "TimeDataLayer- Has labels: " + str(self.haslabels), "QTDC", Qgis.Info
        )
        if self.haslabels:
            self.dolabels = True
        self.capturesettings()

    def resetData(self):
        self.datalist = []
        self.durationarray = []
        self.drawdurations = []

        self.chunksize = 10000
        self.timechunkindex = []
        self.timechunklist = []
        self.endTimechunkindex = []
        self.endTimechunklist = []

    def requestReload(self):
        # Only trigger if reload not already in progress
        if not self.isLoading:
            self.layerReload.emit(self)
        else:
            if self.reLoadable:
                self.layerReload.emit(self)

    def requestClose(self):
        QgsMessageLog.logMessage("Emit CLOSE  " + self.getName(), "TimeDataLayer")
        self.layerClose.emit(self)

    def newFeatures(self, layerid, features):
        QgsMessageLog.logMessage(
            "Got "
            + str(len(features))
            + " new features on layer "
            + self.maplayer.name(),
            "QTDC",
            Qgis.Info,
        )
        self.updateLayer(features)
        self.layerUpdate.emit(self)

    def getName(self):
        return self.maplayer.name()

    def setCRSTransform(self):
        #
        # When the map CRS is changed, the geometry of the data elements also needs to be
        # transformed for proper rendering
        #
        projectCRS = QgsProject.instance().crs()

        # Transform the geometries of this layer to the new CRS if it differs
        # from the original and then set the CRS of this layer to the new one.
        if not self.sourceCRS == projectCRS:
            # If this layer is being transformed, don't do it again.
            if not self.transformTask:
                # TODO: Put this block in a LayerTransformTask object if the datalist
                # is longer than 250K to background it.
                self.coordinateTransform = QgsCoordinateTransform(
                    self.sourceCRS, projectCRS, QgsProject.instance()
                )
                self.sourceCRS = projectCRS
                for p in self.datalist:
                    p.geometryTransform(self.coordinateTransform)

    def transformationDone(self):
        self.transformTask = None

    def capturesettings(self):
        #
        # Capture layer settings and properties
        #
        settings = self.settingsEditor.getsettings()
        if settings:
            try:
                self.dolabels = self.haslabels and settings["dolabels"]
                self.setrenderspeed(settings["hispeed"])
                self.recentlabels = settings["recentlabels"]
                self.labeltime = settings["labeltime"]
                # self.labeloffsets = settings['labeloffsets']
                arglist = settings["labeloffsets"]
                self.decoArgs.loadFromList(arglist)
                self.fademode = settings["fademode"]
            except:
                QgsMessageLog.logMessage("Error getting settings. ", "QTDC", Qgis.Info)

    def editsettings(self):
        settings = self.settingsEditor.editsettings()
        if settings:
            self.capturesettings()

    def refreshed(self):
        #
        # Transform all data to canvas space when 'hispeed' (cached) rendering.  Called when canvas extent changes.
        #
        if self.hispeed:
            for point in self.datalist:
                point.transform(self)
            # QgsMessageLog.logMessage("Canvas refresh", "QTDC", Qgis.Info)

    def setMessageBar(self, mbar):
        self.messageBar = mbar
        try:
            self.layerMarkers.setMessageBar(mbar)
        except:
            QgsMessageLog.logMessage(
                "TimeDataLayer -  Unable to set layerMarkers message bar.",
                "QTDC",
                Qgis.Warning,
            )

    def togglestate(self, s):
        if s:
            self.setvisibility(self.visibleReturn)
        else:
            self.visibleReturn = self.isVisible
            self.setvisibility(s)

    def setLoading(self, loadstate, loadmessage="Loading...", reloadable=False):
        self.isLoading = loadstate
        self.loadBanner = loadmessage
        self.reLoadable = reloadable

    def setvisibility(self, v):
        self.isVisible = v
        self.update()

    def setrenderspeed(self, hispeed):
        #
        # Set the rendering hispeed flag (cached, not cached) and notify the user if cached is selected.
        # With cached rendering, data elements are transformed to canvas space with each extent change.
        # With normal rendering (not cached) transformation is done on the fly.
        #
        self.hispeed = hispeed
        if self.hispeed:
            if self.messageBar:
                self.messageBar.pushMessage(
                    "Cached rendering has been activated."
                    + "  EXPECT DELAYS with map redraw/resizing events.",
                    level=Qgis.Info,
                    duration=5,
                )
            self.refreshed()
            QgsApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            QgsMessageLog.logMessage("Render speed set to HIGH.", "QTDC", Qgis.Info)
        else:
            QgsMessageLog.logMessage("Render speed set to LOW.", "QTDC", Qgis.Info)

    # def success(self):
    # return self.success

    def setdirection(self, d):
        self.fwd = d

    def setSingleSymbol(self):
        #
        # This is called when a single symbol renderer change occurs for the source layer.
        # Update the layer markers according to the new renderer only if the layer
        # is NOT colored by attribute
        #
        self.layerMarkers.ruled = False
        self.layerMarkers.graduated = False
        self.layerMarkers.categorized = False
        self.layerMarkers.setupSymbols(self.maplayer)
        self.basealpha = self.layerMarkers.basealpha
        if (
            not self.layerMarkers.randomized
        ):  # Reset marker index only if NOT randomized
            for dataobject in self.datalist:
                dataobject.setMarkerIndex(0)

    #
    # The following methods classify the layer's geometry
    #
    def isPointLayer(self):
        return self.wkbType in geometryTypes.pointGeometries

    def isLineLayer(self):
        return self.wkbType in geometryTypes.lineGeometries

    def isPolyLayer(self):
        return self.wkbType in geometryTypes.polygonGeometries

    def checkForNewData(self, updatetime):
        QgsMessageLog.logMessage(
            "Check for data since: " + str(updatetime), "QTDC", Qgis.Info
        )
        return True

    def ingestFeatures(self, task, features, totalfeatures, attridx):
        #
        # Ingest the provided features into the layer. Establish marker indexing
        # based on the type of rendering and use the features attributes to determine
        # the correct marker to use when necessary.
        #
        errorct = 0
        fcount = 0
        badRows = 0

        #
        # Get the time stamp and label fields to use
        epochfield = self.loadstate.epochfield
        durationfield = self.loadstate.durationfield
        labelfield = self.loadstate.labelExpression

        QgsMessageLog.logMessage(
            epochfield + "  IS EPOCH IN TIMEDATALAYER", "QTDC", Qgis.Info
        )
        QgsMessageLog.logMessage(
            str(durationfield) + "  IS DURATION", "QTDC", Qgis.Info
        )
        QgsMessageLog.logMessage(str(self.randomized) + "  IS COLOR", "QTDC", Qgis.Info)
        #
        # Set up expression context for processing label expressions
        context = QgsExpressionContext()
        scope = QgsExpressionContextScope()
        context.appendScope(scope)

        # Main feature ingest loop
        for feature in features:
            try:
                geometry = feature.geometry()
                if geometry:

                    fid = feature.id()

                    # Store time internally as float seconds for qt animation function, offset for utc as specified
                    epoch = (
                        self.dateFormatter.parseDate(feature[epochfield])
                        + self.utcOffset
                    )

                    duration = None
                    if durationfield:
                        duration = (
                            self.dateFormatter.parseDate(feature[durationfield])
                            + self.utcOffset
                        )
                        self.useduration = True

                    markerindex = 0
                    #
                    # If a label is specified, get the label value for this feature
                    # Date type fields are formatted by the default format for their type
                    #
                    labelvalue = None
                    if labelfield:
                        scope.setFeature(feature)
                        fieldVal = labelfield.evaluate(context)
                        labelvalue = str(fieldVal)
                        try:
                            if type(fieldVal) is QDateTime:
                                labelvalue = fieldVal.toString(
                                    QgsDateTimeFieldFormatter.DATETIME_FORMAT
                                )
                            elif type(fieldVal) is QDate:
                                labelvalue = fieldVal.toString(
                                    QgsDateTimeFieldFormatter.DATE_FORMAT
                                )
                            elif type(fieldVal) is QTime:
                                labelvalue = fieldVal.toString(
                                    QgsDateTimeFieldFormatter.TIME_FORMAT
                                )
                        except:
                            labelvalue = str(fieldVal)

                    attrvalue = None

                    if self.layerMarkers.randomized:
                        #
                        # For 'color by attribute', use the value of this feature's attribute to get the
                        # marker index for rendering
                        #
                        attrvalue = str(feature.attribute(attridx))
                        markerindex = self.layerMarkers.attrdict.get(attrvalue)
                        if (
                            markerindex == None
                        ):  # The value wasn't found so add a new random symbol for it
                            markerindex = self.layerMarkers.addRandomMarker(attrvalue)

                    elif self.layerMarkers.categorized:
                        #
                        # Use the value of this feature's categorization attribute to get the marker index for rendering
                        #
                        attrvalue = str(feature.attributes()[attridx])
                        # markerindex points to the marker for this attr in the markers array
                        markerindex = self.layerMarkers.attrdict.get(attrvalue)
                        if (
                            markerindex == None
                        ):  # if this item isn't in a known category, use the 'unknown' marker (usually the last)
                            markerindex = len(self.layerMarkers.attrdict) - 1
                    elif self.layerMarkers.graduated:
                        #
                        # Use the value of this feature's symbol graduation attribute to get the marker index for rendering
                        #
                        attrvalue = feature.attribute(attridx)
                        markerindex = self.layerMarkers.getRangeMarkerIndex(attrvalue)
                    elif self.layerMarkers.ruled:
                        #
                        # Get the marker index for rendering by evaluating the rendering rules for this feature
                        markerindex = self.layerMarkers.getRuleMarkerIndex(feature)

                    if markerindex < 0:  # skip to the next feature if no index found
                        self.loadStatusMessage = (
                            self.maplayer.name()
                            + " - Features not rendered under the layer renderer settings have not been loaded."
                        )
                        continue
                    #
                    # Create the appropriate time data element for this feature based on geometry
                    #

                    if self.isPointLayer():
                        point = TimeDataPoint(
                            geometry, fid, markerindex, epoch, duration, labelvalue
                        )
                    elif self.isLineLayer():
                        point = TimeDataLine(
                            geometry,
                            fid,
                            markerindex,
                            self,
                            epoch,
                            duration,
                            labelvalue,
                        )
                    elif self.isPolyLayer():
                        point = TimeDataPolygon(
                            geometry,
                            fid,
                            markerindex,
                            self,
                            epoch,
                            duration,
                            labelvalue,
                        )
                    else:
                        # This shouldn't happen because unsupported layers are not loaded
                        continue

                    # If the coordinateTransform has been set, we need to transform
                    # the geometry so it matches the CRS of the project.
                    if point and self.coordinateTransform:
                        point.geometryTransform(self.coordinateTransform)

                    self.appendPoint(point)

                    #
                    # Update the task progress
                    #
                    fcount += 1
                    if task is not None:
                        progress = (fcount * 100) / totalfeatures
                        task.setProgress(progress)
                        if task.isCanceled():
                            return False, 0
            except Exception as e:
                etype, val, trace = sys.exc_info()
                tbline = trace.tb_lineno

                if errorct < 10:
                    QgsMessageLog.logMessage(
                        "Exception loading FEATURE. " + str(e), "QTDC", Qgis.Info
                    )
                elif (errorct % 100) == 0:
                    QgsMessageLog.logMessage(
                        "Exception loading FEATURE. " + str(e), "QTDC", Qgis.Info
                    )
                badRows += 1
        return True, badRows

    def updateLayer(self, newData, task=None):
        #
        # Update the map layer with newData from the source layer.  TODO: This should be
        # called by a background task.
        # Generally this would be used for live PostGis sources that provide an update signal.
        #

        QgsMessageLog.logMessage(
            "UPDATE LAYER "
            + self.maplayer.name()
            + " with "
            + str(len(newData))
            + " FEATURES",
            "QTDC",
            Qgis.Info,
        )

        #
        # Get various settings established when the layer was loaded.
        #
        epochfield = self.loadstate.epochfield
        durationfield = self.loadstate.durationfield
        labelfield = self.loadstate.labelExpression

        try:
            features = newData
            attridx = self.layerMarkers.getAttributeIndex()
            if (
                self.randomized
            ):  # Color by attribute selected, so get the index of the attribute used
                # This is for Python3, use .fieldNameIndex() for Python2
                attridx = self.maplayer.fields().indexFromName(self.colorattr)
            elif (
                self.layerMarkers.categorized
            ):  # Get the index of the categorization attribute for categorized renderer
                attridx = self.maplayer.fields().indexFromName(
                    self.layerMarkers.catattr
                )

            QgsMessageLog.logMessage(
                "UPDATE LAYER: Got attr idx " + str(attridx), "QTDC", Qgis.Info
            )

            #
            # Set up expression context for processing label expressions
            context = QgsExpressionContext()
            scope = QgsExpressionContextScope()
            context.appendScope(scope)

            errorct = 0
            totalfeatures = len(newData)

            fcount = 0
            badRows = 0

            start_time = time.time()  # DEBUG added
            QgsMessageLog.logMessage("Enter update feature loop", "QTDC", Qgis.Info)

            # Main data ingest method
            retstatus, badrows = self.ingestFeatures(
                task, features, totalfeatures, attridx
            )
            if not retstatus:  # Task was cancelled
                return retstatus

            elapsed_time = time.time() - start_time  # DEBUG
            QgsMessageLog.logMessage(
                "Layer update elapsed time: {:.3f} secs".format(elapsed_time),
                "QTDC",
                Qgis.Info,
            )
            if badRows > 0:
                QgsMessageLog.logMessage(
                    str(badRows)
                    + " features failed to load in layer "
                    + self.maplayer.name(),
                    "QTDC",
                    Qgis.Info,
                )

            # Sort the layer points by time, and generate the parallel time index
            if totalfeatures > 0:
                QgsMessageLog.logMessage(
                    "UPDATE LAYER:  Ordering points.", "QTDC", Qgis.Info
                )
                # The chunk lists will be rebuilt when ordering points
                self.timechunkindex = []
                self.timechunklist = []
                self.endTimechunkindex = []
                self.endTimechunklist = []
                self.orderpoints()
            return True

        except Exception as ee:
            etype, val, trace = sys.exc_info()
            tbline = trace.tb_lineno
            QgsMessageLog.logMessage(
                self.maplayer.name()
                + " failed to load during update. \n"
                + str(etype)
                + " line "
                + str(tbline),
                "QTDC",
                Qgis.Warning,
            )
            raise ee

    def loadmaplayer(self, task, maplayer):
        # This method should be called by a background task.
        #
        # Maplayer is loaded into a point array from the specified map layer by either all
        # features or selected features only. The color of its map symbol will be used for
        # display unless 'color by attribute' is selected. Time info comes from the specified epochfield
        # and is converted to float seconds with multiplier.
        #
        # Symbol properties are generated by LayerMarkers from the layer's renderer

        # Set an arbitrary default histogram color.
        self.histocolor = QColor(100, 100, 200)

        # Get some properties from the load state
        sel = self.loadstate.selectedonly
        epochfield = self.loadstate.epochfield
        durationfield = self.loadstate.durationfield
        labelfield = self.loadstate.labelExpression

        try:
            self.maplayer = maplayer
            QgsMessageLog.logMessage(
                "Loading layer: " + maplayer.name() + " " + str(sel), "QTDC", Qgis.Info
            )
            retstatus = False

            if sel:  # Get only selected features
                features = maplayer.selectedFeatures()
            else:
                features = maplayer.getFeatures()
            if features:
                #
                # Prepare the layer marker properties
                #
                self.layerMarkers = LayerMarkers(
                    self.maplayer, self.randomized, self.colorattr
                )
                self.basealpha = self.layerMarkers.basealpha
                self.histocolor = self.layerMarkers.histocolor
                QgsMessageLog.logMessage("Processing features...", "QTDC", Qgis.Info)
                badRows = 0
                attridx = 0
                attridx = self.layerMarkers.getAttributeIndex()
                if (
                    self.randomized
                ):  # Color by attribute has been selected, so get the attribute to use
                    # This is for Python3, use .fieldNameIndex() for Python2
                    attridx = maplayer.fields().indexFromName(self.colorattr)
                elif (
                    self.layerMarkers.categorized
                ):  # Get the attribute used to categorize symbols with categorized renderer
                    attridx = maplayer.fields().indexFromName(self.layerMarkers.catattr)

                start_time = time.time()  # DEBUG added for timing

                QgsMessageLog.logMessage("Main feature loop...", "QTDC", Qgis.Info)
                QgsApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

                #
                # Set up expression context for processing label expressions
                #
                context = QgsExpressionContext()
                scope = QgsExpressionContextScope()
                context.appendScope(scope)

                errorct = 0
                totalfeatures = maplayer.featureCount()
                fcount = 0

                # Main data ingest method
                retstatus, badrows = self.ingestFeatures(
                    task, features, totalfeatures, attridx
                )

                if not retstatus:  # Task was cancelled
                    return retstatus

                elapsed_time = time.time() - start_time  # DEBUG
                QgsMessageLog.logMessage(
                    "Layer load elapsed time: {:.3f} secs".format(elapsed_time),
                    "QTDC",
                    Qgis.Info,
                )
                if badRows > 0:
                    QgsMessageLog.logMessage(
                        str(badRows)
                        + " features failed to load in layer "
                        + maplayer.name(),
                        "QTDC",
                        Qgis.Info,
                    )

                # Sort the layer points by time, and generate the parallel time index
                self.orderpoints()
                if len(self.datalist) > 0:
                    retstatus = True
                else:
                    raise Exception(
                        "No features were loaded from layer " + maplayer.name()
                    )
            else:
                raise Exception(
                    "No SELECTED features to load in layer " + maplayer.name()
                )
        except Exception as ee:

            etype, val, trace = sys.exc_info()
            tbline = trace.tb_lineno
            QgsMessageLog.logMessage(
                maplayer.name()
                + " failed to load. \n"
                + str(etype)
                + " line "
                + str(tbline),
                "QTDC",
                Qgis.Warning,
            )
            raise ee
        self.success = retstatus
        return retstatus

    def appendPoint(self, pt):
        self.datalist.append(pt)

    def orderpoints(self):
        # TODO:  For duration times, order points by duration end time and build separate
        #       duration time chunk index and chunk list

        self.refreshed()
        QgsMessageLog.logMessage(
            "Feature count..." + str(len(self.datalist)), "QTDC", Qgis.Info
        )

        # Sort the points of the layer by time and generate the parallel time index
        sortedpoints = sorted(
            self.datalist, key=lambda TimeDataElement: TimeDataElement.epoch
        )
        self.datalist = sortedpoints
        # self.timeindex = []

        if self.useduration:
            QgsMessageLog.logMessage("Generate duration array...", "QTDC", Qgis.Info)
            self.durationarray = []
            failCount = 0
            for p in self.datalist:
                try:
                    self.durationarray.append([p.epoch, p.endepoch])
                except:
                    failCount += 1
            self.durationarray = np.asarray(self.durationarray)
            QgsMessageLog.logMessage(
                "duration array size..."
                + str(self.durationarray.size)
                + ", "
                + str(failCount)
                + " FAILED records.",
                "QTDC",
                Qgis.Info,
            )
        else:
            # The time index is arranged in a list of chunks that are
            # referenced by a chunk index during animation
            timechunk = []
            pointct = 0
            for p in self.datalist:
                timechunk.append(p.epoch)
                pointct = pointct + 1
                if (pointct % self.chunksize) == 0:
                    self.timechunklist.append(timechunk)
                    self.timechunkindex.append(p.epoch)
                    timechunk = []

            if not (pointct % self.chunksize) == 0:
                self.timechunklist.append(timechunk)
            QgsMessageLog.logMessage(
                "Ordered points: "
                + str(pointct)
                + " in "
                + str(len(self.timechunklist))
                + " chunks.",
                "QTDC",
                Qgis.Info,
            )

    def getdurationindex(self):
        return self.durationarray

    def isdurationlayer(self):
        return self.useduration

    def gettimeindex(self):
        #
        # Return a flat time index for the layer - used to generate the histogram
        #
        if self.useduration:
            return self.durationarray[..., 0]
        else:
            # Return a flat time index from the stack of chunks
            return [item for chunk in self.timechunklist for item in chunk]

    def getmintime(self):
        #
        # Get the minimum time tag for this layer.
        #
        if self.useduration:
            # Must call 'item' to get native Python object
            result = self.durationarray[0][0].item()
            return result - self.timeshift
        else:
            result = self.timechunklist[0][0]
            return result - self.timeshift

    def getmaxtime(self):
        #
        # Get the maximum time tag for this layer
        #
        if self.useduration:
            # Must call 'item' to get native Python object
            result = np.amax(self.durationarray, 0)[1].item()
            return result - self.timeshift
        else:
            maxchunk = len(self.timechunklist) - 1
            maxtime = len(self.timechunklist[maxchunk]) - 1
            result = self.timechunklist[maxchunk][maxtime]
            return result - self.timeshift

    def setColor(self, color):
        self.pen.setColor(color)

    def getColor(self):
        return self.histocolor

    def settime(self, ctime):

        # Clear the indices and abort if loading in progress
        if self.isLoading:
            self.startindex = 0
            self.endindex = 0
            return 0

        # If this layer is not visible, return the max/min values as the no-data-time (ndt)
        # This will allow skip gaps to ignore data in this layer
        if not self.isVisible:
            if self.fwd:
                return sys.maxsize
            else:
                return 1
        #
        # Set the display time interval for this layer and determine the data indices for the
        # first and last data elements in the interval.
        #
        self.ctime = ctime + self.timeshift
        starttime = self.ctime - self.history
        #
        # Processing for elements with start and end time attributes (duration)
        #
        if self.useduration:
            ndt = 0
            self.drawdurations = np.argwhere(
                (starttime <= self.durationarray[:, 1])
                & (self.durationarray[:, 0] <= self.ctime)
            )
            if len(self.drawdurations) < 1:
                if self.fwd:
                    nextdurations = np.argwhere((starttime <= self.durationarray[:, 1]))
                    if len(nextdurations) > 0:
                        i = nextdurations[0][0]
                        ndt = self.durationarray[i][0]
                    else:
                        di = self.durationarray.shape[0] - 1
                        ndt = self.durationarray[di][1]
                else:
                    nextdurations = np.argwhere(
                        (self.durationarray[:, 0] <= self.ctime)
                    )
                    if len(nextdurations) > 0:
                        di = nextdurations.shape[0] - 1
                        i = nextdurations[di][0]
                        ndt = self.durationarray[i][1]
                    else:
                        ndt = self.durationarray[0][0]
                ndt = ndt - self.timeshift
            return ndt
        #
        # Processing for elements with a single time tag
        #
        else:
            self.incr = 1
            startchunk = 0
            endchunk = 0
            try:
                #
                # Find the chunk containing the start/end times
                #
                startchunk = np.searchsorted(
                    self.timechunkindex, starttime, side="left"
                )
                endchunk = np.searchsorted(
                    self.timechunkindex, self.ctime, side="right"
                )

                chunklimit = len(self.timechunklist)
                if endchunk >= chunklimit:
                    endchunk = chunklimit - 1
                if startchunk >= chunklimit:
                    startchunk = chunklimit - 1

                #
                # Find the data indices for start/end time in the chunks found above
                #
                if self.fwd:
                    self.startindex = np.searchsorted(
                        self.timechunklist[startchunk], starttime, side="left"
                    )
                    self.endindex = np.searchsorted(
                        self.timechunklist[endchunk], self.ctime, side="right"
                    )
                else:
                    self.endindex = np.searchsorted(
                        self.timechunklist[startchunk], starttime, side="left"
                    )
                    self.startindex = np.searchsorted(
                        self.timechunklist[endchunk], self.ctime, side="right"
                    )
                    scratch = startchunk
                    startchunk = endchunk
                    endchunk = scratch
                    self.incr = -1
                    self.startindex = self.startindex - 1
                    self.endindex = self.endindex - 1

            except IndexError as ie:
                QgsMessageLog.logMessage(
                    "Chunk index error: Start chunk: "
                    + str(startchunk)
                    + "; End chunk: "
                    + str(endchunk)
                    + "; Index size: "
                    + str(len(self.timechunklist)),
                    "QTDC",
                    Qgis.Warning,
                )

            ndt = 0

            # if startindex = endindex there may be no data in this layer at this time
            if (self.startindex == self.endindex) and (startchunk == endchunk):
                nextdataindex = min(
                    self.startindex, ((len(self.timechunklist[startchunk])) - 1)
                )
                if self.fwd:
                    ndt = self.timechunklist[startchunk][nextdataindex]
                else:
                    if self.startindex > 0:
                        nextdataindex = nextdataindex - 1
                    ndt = self.timechunklist[startchunk][nextdataindex]
                ndt = ndt - self.timeshift
            else:
                ndt = 0

            # TODO: For duration time processing, also find start and
            #       end index for duration end time chunk lists and set the display
            #       start index to the minimum and end index to the maximum of the indexes.

            # Need to offset the start and end indices by the number of chunks.
            # They refer to the data within the chunk.
            self.startindex = self.startindex + (startchunk * self.chunksize)
            self.endindex = self.endindex + (endchunk * self.chunksize)
            return ndt

    def sethistory(self, hist):
        self.history = hist
        self.starttime = self.ctime - self.history

    def clearfilter(self):
        self.maplayer.setSubstring("")

    def getWindowDataIds(self):
        idList = []
        name = self.maplayer.name()
        if self.isVisible:
            if self.useduration:
                for i in range(len(self.drawdurations)):
                    ddx = self.drawdurations[i][0]
                    idList.append(self.datalist[ddx].fid)
            else:
                limit = len(self.datalist)
                if self.startindex < limit and self.endindex < limit:
                    for pdx in range(self.startindex, self.endindex, self.incr):
                        idList.append(self.datalist[pdx].fid)
        return idList

    def getdisplayextent(self):
        #
        # Get the extent of the data in the current time window.
        #
        dataenvelope = None
        if self.isVisible:
            geometries = []
            if self.useduration:
                for i in range(len(self.drawdurations)):
                    ddx = self.drawdurations[i][0]
                    geometries.extend(self.datalist[ddx].geometrypoints())
            else:
                for pdx in range(self.startindex, self.endindex, self.incr):
                    geometries.extend(self.datalist[pdx].geometrypoints())
            if len(geometries) > 1:
                dataenvelope = QgsRectangle()
                for g in geometries:
                    dataenvelope.combineExtentWith(g)

                self.canvas.setExtent(dataenvelope)
                self.canvas.zoomOut()
                QgsMessageLog.logMessage(dataenvelope.asWktPolygon(), "QTDC", Qgis.Info)
            elif len(geometries) == 1:
                canvasextent = self.canvas.extent()
                centerpt = canvasextent.center()
                newcenter = geometries[0]
                movevector = newcenter - centerpt
                canvasextent += movevector
                self.canvas.setExtent(canvasextent)
                self.canvas.refresh()

    def paint(self, qp, x, xx):
        starttime = self.ctime - self.history

        if self.isVisible and not self.isLoading:
            qp.setPen(self.pen)
            origxform = qp.transform()
            if self.useduration:
                for i in range(len(self.drawdurations)):
                    ddx = self.drawdurations[i][0]
                    markerindex = self.datalist[ddx].markeridx
                    if self.isPointLayer():
                        qp.setPen(self.layerMarkers.markerProperties[markerindex].color)
                        if (
                            self.layerMarkers.categorized
                            or self.layerMarkers.randomized
                            or self.layerMarkers.graduated
                            or self.layerMarkers.ruled
                        ):
                            ptmarker = self.layerMarkers.markerProperties[
                                markerindex
                            ].markerImage
                            paintxform = self.layerMarkers.markerProperties[
                                markerindex
                            ].paintxform
                        else:
                            ptmarker = self.layerMarkers.markerProperties[0].markerImage
                            paintxform = self.layerMarkers.markerProperties[
                                0
                            ].paintxform
                    elif self.isLineLayer():
                        qp.setPen(self.layerMarkers.markerProperties[markerindex].pen)
                        ptmarker = None
                        paintxform = None
                    elif self.isPolyLayer():
                        ptmarker = None
                        paintxform = None
                        qp.setPen(self.layerMarkers.markerProperties[markerindex].pen)
                        qp.setBrush(
                            self.layerMarkers.markerProperties[markerindex].brush
                        )
                    qp.setOpacity(self.basealpha)
                    if self.hispeed:
                        self.datalist[ddx].draw(
                            self,
                            qp,
                            paintxform,
                            ptmarker,
                            self.basealpha,
                            self.decoArgs,
                            self.dolabels,
                        )
                    else:
                        self.datalist[ddx].transformdraw(
                            self,
                            qp,
                            paintxform,
                            ptmarker,
                            self.basealpha,
                            self.decoArgs,
                            self.dolabels,
                        )
                    qp.setTransform(origxform)
            else:
                element = []
                for pdx in range(self.startindex, self.endindex, self.incr):
                    pointtime = self.datalist[pdx].epoch - starttime
                    if not self.fwd:
                        pointtime = self.history - pointtime
                    if not self.fademode:
                        alpha = self.basealpha
                    else:
                        alpha = (
                            (pointtime) / self.history
                        ) * self.basealpha  # Limit alpha to base alpha

                    markerindex = self.datalist[pdx].markeridx
                    # QgsMessageLog.logMessage("marker index: " + str(markerindex), "QTDC")
                    if self.isPointLayer():
                        if (
                            self.layerMarkers.randomized
                            or self.layerMarkers.categorized
                            or self.layerMarkers.graduated
                            or self.layerMarkers.ruled
                        ):
                            ptmarker = self.layerMarkers.markerProperties[
                                markerindex
                            ].markerImage
                            paintxform = self.layerMarkers.markerProperties[
                                markerindex
                            ].paintxform
                            qp.setOpacity(alpha)
                        else:
                            ptmarker = self.layerMarkers.markerProperties[0].markerImage
                            paintxform = self.layerMarkers.markerProperties[
                                0
                            ].paintxform
                        qp.setPen(self.layerMarkers.markerProperties[markerindex].color)
                    elif self.isLineLayer():
                        qp.setPen(self.layerMarkers.markerProperties[markerindex].pen)
                        ptmarker = None
                        paintxform = None
                    elif self.isPolyLayer():
                        ptmarker = None
                        paintxform = None
                        qp.setPen(self.layerMarkers.markerProperties[markerindex].pen)
                        qp.setBrush(
                            self.layerMarkers.markerProperties[markerindex].brush
                        )

                    qp.setOpacity(alpha)
                    element = [qp, paintxform, ptmarker, alpha]

                    showthislabel = self.dolabels
                    if self.recentlabels and self.dolabels:
                        showthislabel = (self.history - pointtime) <= self.labeltime
                    if self.hispeed:
                        self.datalist[pdx].draw(
                            self,
                            qp,
                            paintxform,
                            ptmarker,
                            alpha,
                            self.decoArgs,
                            showthislabel,
                        )
                    else:
                        self.datalist[pdx].transformdraw(
                            self,
                            qp,
                            paintxform,
                            ptmarker,
                            alpha,
                            self.decoArgs,
                            showthislabel,
                        )

                if len(element) >= 4:
                    if self.hispeed:
                        self.datalist[pdx].draw(
                            self,
                            element[0],
                            element[1],
                            element[2],
                            element[3],
                            self.decoArgs,
                            self.dolabels,
                        )
                    else:
                        self.datalist[pdx].transformdraw(
                            self,
                            element[0],
                            element[1],
                            element[2],
                            element[3],
                            self.decoArgs,
                            self.dolabels,
                        )

    def updatePosition(self):
        mapextent = self.canvas.extent()
        self.transform = self.canvas.transform()
        self.setRect(mapextent)

#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import random
import time

from qgis.PyQt import QtGui, QtCore
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import QDialog

from qgis.core import QgsApplication, QgsPointXY, QgsGeometry

from qgis.core import (
    Qgis,
    QgsRectangle,
    QgsRenderContext,
    QgsSingleSymbolRenderer,
    QgsCategorizedSymbolRenderer,
    QgsGraduatedSymbolRenderer,
    QgsRuleBasedRenderer,
    QgsMessageLog,
    QgsWkbTypes,
    QgsExpressionContext,
    QgsExpressionContextScope,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsProject,
    QgsCoordinateTransform,
)

from .SymbolRangeItem import SymbolRangeItem
from .LayerMarkerObject import markerObject
from .GeometryTypes import geometryTypes
from .QtdcExceptions import *


class LayerMarkers:
    def __init__(self, maplayer, randomized, colorattr):

        self.markerProperties = []
        self.attrdict = {}

        self.maplayer = maplayer
        self.randomized = randomized
        self.colorattr = colorattr

        self.graduated = False

        self.histocolor = QColor(100, 100, 200)
        self.wkbType = self.maplayer.wkbType()

        self.categorized = False
        self.ruled = False
        self.setupSymbols(maplayer)

    def setupSymbols(self, maplayer):
        renderer = self.maplayer.renderer()

        if isinstance(renderer, QgsCategorizedSymbolRenderer):
            if self.randomized:
                raise LayerMarkerException(
                    "Categorized symbol renderer cannot be combined with color by attribute TDC setting."
                )
            QgsMessageLog.logMessage(
                "Layer has CATEGORIZED renderer... " + maplayer.name(),
                "QTDC",
                Qgis.Info,
            )
            self.markerProperties = []
            self.getcategorizedsymbols(renderer)
            self.categorized = True

        elif isinstance(renderer, QgsRuleBasedRenderer):
            if self.randomized:
                raise LayerMarkerException(
                    "Rule-based symbol renderer cannot be combined with color by attribute TDC setting."
                )
            QgsMessageLog.logMessage("Rule based renderer", "QTDC", Qgis.Info)
            root_rule = renderer.rootRule()
            self.rulelist = root_rule.children()
            self.markerProperties = []
            self.ruleSymbolDict = {}
            QgsMessageLog.logMessage("Checking for rules...", "QTDC", Qgis.Info)
            if len(self.rulelist) > 0:
                for rule in self.rulelist:
                    rulekey = rule.ruleKey()
                    QgsMessageLog.logMessage("RULE FOUND", "QTDC", Qgis.Info)
                    marker = self.getSymbolImage(rule.symbol(), rule.symbol().color())
                    QgsMessageLog.logMessage(
                        "Got symbol properties...", "QTDC", Qgis.Info
                    )
                    self.markerProperties.append(marker)
                    self.ruleSymbolDict[rulekey] = self.markerProperties.index(marker)
                    QgsMessageLog.logMessage(
                        "Rule Symbol Index " + str(self.markerProperties.index(marker)),
                        "QTDC",
                        Qgis.Info,
                    )
                self.ruled = True
            else:
                raise LayerMarkerException(
                    "No rules found for layer " + maplayer.name()
                )

        elif isinstance(renderer, QgsGraduatedSymbolRenderer):
            if self.randomized:
                raise LayerMarkerException(
                    "Graduated symbols cannot be used with color by attribute TDC setting."
                )
            QgsMessageLog.logMessage(
                "Layer has GRADUATED renderer... " + maplayer.name(), "QTDC", Qgis.Info
            )
            self.graduated = True
            rangeattr = renderer.classAttribute()
            self.markerProperties = []
            self.rangeitems = []
            QgsMessageLog.logMessage(
                "Building graduated symbol collection.", "QTDC", Qgis.Info
            )
            for r in renderer.ranges():
                marker = self.getSymbolImage(r.symbol(), r.symbol().color())
                self.markerProperties.append(marker)
                rangeitem = SymbolRangeItem(r, self.markerProperties.index(marker))
                self.rangeitems.append(rangeitem)

        elif isinstance(renderer, QgsSingleSymbolRenderer):
            QgsMessageLog.logMessage(
                "Layer has single symbol renderer... " + maplayer.name(),
                "QTDC",
                Qgis.Info,
            )
            layersymbol = maplayer.renderer().symbol().clone()
            color = layersymbol.color()
            self.histocolor = color
            # self.basealpha = color.alphaF()
            self.basealpha = layersymbol.opacity()

            QgsMessageLog.logMessage(
                str(self.basealpha) + "  BASE ALPHA", "QTDC", Qgis.Info
            )
            QgsMessageLog.logMessage(
                str(layersymbol.symbolLayerCount()) + "  SYMBOL LAYER COUNT",
                "QTDC",
                Qgis.Info,
            )
            if self.randomized:
                QgsMessageLog.logMessage(
                    "Randomizing colors... " + maplayer.name(), "QTDC", Qgis.Info
                )
                self.random_markers(layersymbol)
            else:
                markerimage = self.getSymbolImage(layersymbol, color)
                self.markerProperties = [markerimage]
                QgsMessageLog.logMessage("Single marker... ", "QTDC", Qgis.Info)
        else:
            raise LayerMarkerException("Renderer type not supported by TDC.")

    def setMessageBar(self, mb):
        self.messageBar = mb

    def isPointLayer(self):
        return self.wkbType in geometryTypes.pointGeometries

    def isLineLayer(self):
        return self.wkbType in geometryTypes.lineGeometries

    def isPolyLayer(self):
        return self.wkbType in geometryTypes.polygonGeometries

    def getRangeMarkerIndex(self, value):
        for item in self.rangeitems:
            if (value >= item._lower) and (value <= item._upper):
                return item._markerindex
        return -1  # range not found for value

    def getRuleMarkerIndex(self, feature):
        # return the rule symbol index for the first rule that passes for the feature
        for rule in reversed(
            self.rulelist
        ):  # evaluate active rules in reverse order to match rendering order
            if rule.isFilterOK(feature, QgsRenderContext()) and rule.active():
                rulekey = rule.ruleKey()
                ruleindex = self.ruleSymbolDict[rulekey]
                return ruleindex
        return -1  # None of the rules passed

    def getAttributeIndex(self):
        renderer = self.maplayer.renderer()
        if isinstance(renderer, QgsGraduatedSymbolRenderer):
            attrname = renderer.classAttribute()
            return self.maplayer.fields().indexFromName(attrname)
        return 0

    def random_markers(self, s):
        # self.colors.append(color)
        # Set the first symbol
        basemarker = self.getSymbolImage(s)
        self.markerProperties = [basemarker]

        if self.colorattr:
            """
            Create an array of randomly colored markers and a dictionary for attribute values.
            The array is needed since ordering is not guaranteed for dictionaries, and
            only the index of the marker is stored in the time data point.
            The dictionary is used during data load to find the color index for the feature's attribute value.
            The marker array is indexed during paint by the marker index stored with each data point.
            """
            self.markerProperties = []
            begintime = time.time()

            symbol = s.clone()

            if self.isPointLayer():
                markersize = self.getMarkerSize(symbol)

            # self.markertable = []
            colortable = []
            for i in range(0, 359):
                h = i
                s = max(int(random.random() * 255), 90)
                l = max(int(random.random() * 255), 100)
                color = QColor.fromHsl(h, s, l)

                symbol.setColor(color)
                colortable.append(color)
                marker = self.getSymbolImage(symbol, color)
                self.markerProperties.append(marker)

            ticktime = time.time() - begintime
            QgsMessageLog.logMessage(
                " Color table time: " + str(ticktime), "QTDC", Qgis.Info
            )
            QgsApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            begintime = time.time()

            # Get the unique values for the attribute
            fldidx = self.maplayer.fields().indexFromName(self.colorattr)
            values = self.maplayer.uniqueValues(fldidx)
            # Create a random color and marker for each of the unique values
            i = 0
            for value in values:
                tableindex = int(random.random() * 359)

                # Put the attribute value and corresponding marker index in the marker dictionary
                self.attrdict[str(value)] = tableindex
                i = i + 1

            ticktime = time.time() - begintime
            QgsMessageLog.logMessage(
                " Symbol dictionary time: " + str(ticktime), "QTDC", Qgis.Info
            )
            QgsApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

    def addRandomMarker(self, strvalue):
        tableindex = int(random.random() * 359)
        self.attrdict[strvalue] = tableindex
        return tableindex

    def getcategorizedsymbols(self, renderer):

        """
        This method creates a dictionary of symbols for the layer using the
        symbols contained in its 'Categorized Renderer'.  The symbol array also
        needs to contain the display transform to keep symbols properly centered
        when they are not all the same size.
        """
        self.catattr = renderer.classAttribute()
        categories = renderer.categories()
        if len(categories) > 0:
            for category in categories:
                symbol = category.symbol()
                value = category.value()
                label = category.label()
                markerimage = self.getSymbolImage(
                    symbol
                )  # This returns an object containing a symbol image and display transform
                self.markerProperties.append(markerimage)
                self.attrdict[str(value)] = self.markerProperties.index(markerimage)
        else:
            raise LayerMarkerException(
                "Rendering category classes have not been defined for layer."
            )

    def setSymbol(self):
        try:
            renderer = self.maplayer.renderer()

            QgsMessageLog.logMessage("Setting symbol...", "QTDC", Qgis.Info)
            if isinstance(renderer, QgsSingleSymbolRenderer):
                layersymbol = renderer.symbol().clone()
                self.categorized = False
                if not self.randomized:
                    color = layersymbol.color()
                    markerimage = self.getSymbolImage(layersymbol, color)
                    if len(self.markerProperties) > 0:
                        for i in range(len(self.markerProperties)):
                            self.markerProperties[i] = markerimage
                    else:
                        self.markerProperties = [markerimage]

            elif isinstance(renderer, QgsCategorizedSymbolRenderer):
                if self.messageBar:
                    self.messageBar.pushMessage(
                        "The layer "
                        + self.maplayer.name()
                        + " must be reloaded for the renderer changes to appear in animation.",
                        level=Qgis.Info,
                        duration=5,
                    )

        except Exception as e:
            QgsMessageLog.logMessage(
                "Exception setting layer symbol. " + str(e), "QTDC", Qgis.Warning
            )
            raise LayerMarkerException(str(e))

    def getMarkerSize(self, layersymbol):
        outunits = layersymbol.outputUnit()
        mus = layersymbol.mapUnitScale()
        # This line is a bit of a hack to get it to appear correctly on the map, needs further work
        punits = (
            QgsRenderContext().convertToPainterUnits(
                layersymbol.size() * 2, outunits, mus
            )
            + layersymbol.size() * 2
        )
        painterunits = int(punits)
        markersize = QSize(painterunits, painterunits)
        return markersize

    def getSymbolImage(self, layersymbol, color=None):

        marker = markerObject()
        self.basealpha = layersymbol.opacity()
        if self.isPointLayer():
            # The following is intended to get a Qimage of the layer's symbol at the correct size
            if color:
                layersymbol.setColor(color)

            outunits = layersymbol.outputUnit()
            mus = layersymbol.mapUnitScale()

            # This line is a bit of a hack to get it to appear correctly on the map, needs further work
            punits = (
                QgsRenderContext().convertToPainterUnits(
                    layersymbol.size() * 2, outunits, mus
                )
                + layersymbol.size() * 2
            )
            painterunits = int(punits)
            markersize = QSize(painterunits, painterunits)
            marker.markerImage = layersymbol.asImage(markersize)
            marker.color = layersymbol.color()

            marker.paintxform = QTransform()
            marker.paintxform.translate(-painterunits / 2, -painterunits / 2)

        elif self.isLineLayer():
            if color:
                layersymbol.setColor(color)

            outunits = layersymbol.outputUnit()
            mus = layersymbol.mapUnitScale()

            # This line is a bit of a hack to get it to appear correctly on the map, needs further work
            painterunits = (
                QgsRenderContext().convertToPainterUnits(
                    layersymbol.width() * 2, outunits, mus
                )
                + layersymbol.width() * 2
            )
            marker.pen = QPen(layersymbol.color(), painterunits)
        elif self.isPolyLayer():

            if isinstance(layersymbol.symbolLayer(0), QgsSimpleFillSymbolLayer):
                sLayer = layersymbol.symbolLayer(0)
                brush = QBrush(sLayer.dxfBrushStyle())
                brush.setColor(sLayer.fillColor())

                outunits = layersymbol.outputUnit()
                mus = layersymbol.mapUnitScale()
                painterunits = (
                    QgsRenderContext().convertToPainterUnits(
                        sLayer.strokeWidth() * 4, outunits, mus
                    )
                    + sLayer.strokeWidth() * 4
                )
                # pen.setWidth(painterunits)
                # self.histocolor = sLayer.fillColor()

                pen = QPen(layersymbol.color(), painterunits)
                marker.pen = pen
                marker.brush = brush
            else:
                sLayer = layersymbol.symbolLayer(0)
                brush = QBrush(sLayer.dxfBrushStyle())
                brush.setColor(sLayer.fillColor())
                # pen = QPen(sLayer.strokeStyle())
                pen = QPen(sLayer.fillColor())
                # pen.setColor(sLayer.strokeColor())
                marker.pen = pen
                marker.brush = brush
        return marker

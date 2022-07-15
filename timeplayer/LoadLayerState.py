#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import json
from qgis.core import QgsMessageLog, QgsExpression


class LoadLayerState:
    def __init__(self):
        self.maplayer = None
        self.dateFormatter = None
        self.epochfield = ""
        self.utcOffset = 0
        self.selectedonly = False
        self.labelExpression = None
        self.durationfield = None
        self.colorattr = ""
        self.timecrtfield = ""
        pass

    def asString(self):
        result = "\nEpoch field: " + str(self.epochfield) + "\n"
        result = result + "Duration field: " + str(self.durationfield) + "\n"
        result = result + "UTC offset: " + str(self.utcOffset) + "\n"
        if self.labelExpression != None:
            result = result + "Label: " + str(self.labelExpression.expression()) + "\n"
        else:
            result = result + "Label: " + str(self.labelExpression) + "\n"
        result = result + "Color attr: " + str(self.colorattr) + "\n"
        result = result + "Load selected: " + str(self.selectedonly) + "\n"
        return result

    def asJson(self):
        return json.dumps(
            {
                "epoch_field": self.epochfield,
                "duration_field": self.durationfield,
                "utc_offset": self.utcOffset,
                "label_expression": None
                if self.labelExpression == None
                else self.labelExpression.expression(),
                "color_attribute": self.colorattr,
                "load_selected_only": self.selectedonly,
            }
        )

    def loadJson(self, jsonStr):
        jsonObj = json.loads(jsonStr)
        self.epochfield = jsonObj["epoch_field"]
        self.durationfield = jsonObj["duration_field"]
        self.utcOffset = jsonObj["utc_offset"]
        self.labelExpression = QgsExpression(jsonObj["label_expression"])
        self.colorattr = jsonObj["color_attribute"]
        self.selectedonly = jsonObj["load_selected_only"]
        return

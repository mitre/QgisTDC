#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

from qgis.PyQt import QtCore
from qgis.PyQt.QtCore import QObject

#
# This class is a container for some of the items needed for basic marker rendering.
#
class markerObject(QObject):
    def __init__(self):
        self.markerImage = None
        self.paintxform = None
        self.color = None
        self.pen = None
        self.brush = None

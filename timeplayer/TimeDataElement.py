#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

from qgis.core import *
from qgis.PyQt import QtCore


class TimeDataElement(object):
    def __init__(self, epoch, endepoch=None):
        self._epoch = epoch
        if endepoch:
            self._endepoch = endepoch

    @property
    def epoch(self):
        return self._epoch

    @property
    def endepoch(self):
        return self._endepoch

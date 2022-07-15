#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#


class SymbolRangeItem(object):
    def __init__(self, range, index):
        self._lower = range.lowerValue()
        self._upper = range.upperValue()
        self._markerindex = index

# -*- coding: utf-8 -*-

"""

This software was produced for the U. S. Government under Contract No. FA8702-19-C-0001, and is subject to the Rights in Noncommercial Computer Software and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
(c) 2020 The MITRE Corporation. All Rights Reserved.

"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .QgisTDC import QgisTDC

    return QgisTDC(iface)

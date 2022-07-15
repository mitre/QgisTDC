#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import os

from PyQt5 import uic
from PyQt5 import QtWidgets


FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "TimeWindowSettings.ui")
)

# Simple dialog for specifying time window limits


class TimeWindowSettingsDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(TimeWindowSettingsDialog, self).__init__(parent)

        self.setupUi(self)
        self.setModal(True)
        self.setWindowTitle("Time Window Limits")
        self.startTimeEdit.setCalendarPopup(True)
        self.endTimeEdit.setCalendarPopup(True)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.initialized = False

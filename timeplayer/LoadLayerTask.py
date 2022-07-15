#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#

import random
from time import sleep

from qgis.PyQt.QtWidgets import QMessageBox

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsTask,
    QgsMessageLog,
)

MESSAGE_CATEGORY = "QTDC"


class LoadLayerTask(QgsTask):
    """QgsTask for loading a layer into the TDC"""

    def __init__(self, description, maplayer, destlayer, callback):
        super().__init__(description, QgsTask.CanCancel)

        self.setProgress(0)
        self.exception = None

        self.maplayer = maplayer
        self.callback = callback
        self.timedatalayer = destlayer

    def run(self):
        """
        Perform layer loading and return a success boolean accordingly
        """
        QgsMessageLog.logMessage(
            'Started task "{}"'.format(self.description()), MESSAGE_CATEGORY
        )
        success = False
        try:
            success = self.timedatalayer.loadmaplayer(self, self.maplayer)
        except Exception as e:
            QgsMessageLog.logMessage("Caught exception in task run.", "QTDC")
            self.exception = e
        return success

    def finished(self, result):
        """
        On task completion, call the 'callback' with the loaded layer if successful.
        If not successful, present the log message.
        """
        if result:
            QgsMessageLog.logMessage(
                'Task "{name}" completed\n'.format(name=self.description()),
                MESSAGE_CATEGORY,
            )
            self.callback(self.timedatalayer)
        else:
            if self.exception is None:
                self.timedatalayer.setLoading(True, "Canceled.", True)
                QgsMessageLog.logMessage(
                    'Task "{name}"  was '
                    "canceled by the user".format(name=self.description()),
                    MESSAGE_CATEGORY,
                )
            else:
                self.timedatalayer.setLoading(True, "Failed.", True)
                QgsMessageLog.logMessage(
                    'Task "{name}" Exception: {exception}'.format(
                        name=self.description(), exception=self.exception
                    ),
                    MESSAGE_CATEGORY,
                )

                mbox = QMessageBox()
                mbox.setIcon(QMessageBox.Critical)
                mbox.setText(str(self.exception))
                ret = mbox.exec_()
                # raise self.exception
        self.timedatalayer = None

    def cancel(self):
        """
        Called when the user cancels the load operation.
        """
        QgsMessageLog.logMessage(
            'Task "{name}" was canceled'.format(name=self.description()),
            MESSAGE_CATEGORY,
        )
        super().cancel()

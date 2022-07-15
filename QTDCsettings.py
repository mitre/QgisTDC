# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'QTDCsettings.ui'
#
# Created by: PyQt5 UI code generator 5.15.4
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_QTDC_Settings(object):
    def setupUi(self, QTDC_Settings):
        QTDC_Settings.setObjectName("QTDC_Settings")
        QTDC_Settings.resize(493, 265)
        self.verticalLayout = QtWidgets.QVBoxLayout(QTDC_Settings)
        self.verticalLayout.setObjectName("verticalLayout")
        self.groupBox = QtWidgets.QGroupBox(QTDC_Settings)
        self.groupBox.setObjectName("groupBox")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.groupBox)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.showInfoTextBox = QtWidgets.QCheckBox(self.groupBox)
        self.showInfoTextBox.setChecked(True)
        self.showInfoTextBox.setObjectName("showInfoTextBox")
        self.horizontalLayout.addWidget(self.showInfoTextBox)
        self.label = QtWidgets.QLabel(self.groupBox)
        self.label.setAlignment(
            QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter
        )
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.textSizeSpinner = QgsSpinBox(self.groupBox)
        self.textSizeSpinner.setMinimum(5)
        self.textSizeSpinner.setMaximum(24)
        self.textSizeSpinner.setProperty("value", 8)
        self.textSizeSpinner.setObjectName("textSizeSpinner")
        self.horizontalLayout.addWidget(self.textSizeSpinner)
        self.label_2 = QtWidgets.QLabel(self.groupBox)
        self.label_2.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.label_2.setAlignment(
            QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter
        )
        self.label_2.setObjectName("label_2")
        self.horizontalLayout.addWidget(self.label_2)
        self.textColorButton = QgsColorButton(self.groupBox)
        self.textColorButton.setObjectName("textColorButton")
        self.horizontalLayout.addWidget(self.textColorButton)
        self.verticalLayout.addWidget(self.groupBox)
        self.ImageCaptureGroup = QtWidgets.QGroupBox(QTDC_Settings)
        self.ImageCaptureGroup.setObjectName("ImageCaptureGroup")
        self.gridLayout = QtWidgets.QGridLayout(self.ImageCaptureGroup)
        self.gridLayout.setObjectName("gridLayout")
        self.label_3 = QtWidgets.QLabel(self.ImageCaptureGroup)
        self.label_3.setObjectName("label_3")
        self.gridLayout.addWidget(self.label_3, 0, 0, 1, 1)
        self.captureFolderChooser = QgsFileWidget(self.ImageCaptureGroup)
        self.captureFolderChooser.setObjectName("captureFolderChooser")
        self.gridLayout.addWidget(self.captureFolderChooser, 1, 0, 1, 1)
        self.label_4 = QtWidgets.QLabel(self.ImageCaptureGroup)
        self.label_4.setObjectName("label_4")
        self.gridLayout.addWidget(self.label_4, 2, 0, 1, 1)
        self.capturePrefixText = QtWidgets.QLineEdit(self.ImageCaptureGroup)
        self.capturePrefixText.setObjectName("capturePrefixText")
        self.gridLayout.addWidget(self.capturePrefixText, 3, 0, 1, 1)
        self.verticalLayout.addWidget(self.ImageCaptureGroup)
        self.buttonBox = QtWidgets.QDialogButtonBox(QTDC_Settings)
        self.buttonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok
        )
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(QTDC_Settings)
        QtCore.QMetaObject.connectSlotsByName(QTDC_Settings)

    def retranslateUi(self, QTDC_Settings):
        _translate = QtCore.QCoreApplication.translate
        QTDC_Settings.setWindowTitle(_translate("QTDC_Settings", "Settings"))
        self.groupBox.setTitle(_translate("QTDC_Settings", "TDC Map Text "))
        self.showInfoTextBox.setText(_translate("QTDC_Settings", "Show Text"))
        self.label.setText(_translate("QTDC_Settings", "Size:"))
        self.label_2.setText(_translate("QTDC_Settings", "Color:"))
        self.ImageCaptureGroup.setTitle(
            _translate("QTDC_Settings", "Map Image Capture")
        )
        self.label_3.setText(_translate("QTDC_Settings", "Folder:"))
        self.label_4.setText(_translate("QTDC_Settings", "File name prefix:"))


from qgscolorbutton import QgsColorButton
from qgsfilewidget import QgsFileWidget
from qgsspinbox import QgsSpinBox
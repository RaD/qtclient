# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from PyQt4.QtGui import *
from PyQt4.QtCore import *

class DlgCalendar(QDialog):

    def __init__(self, parent=None, **kwargs):
        QDialog.__init__(self, parent)

        self.parent = parent
        self.setMinimumWidth(400)

        date_range = kwargs.get('date_range', None)
        title = kwargs.get('title', self.tr('Set the title'))
        desc = kwargs.get('desc', None)

        self.calendar = QCalendarWidget()
        self.calendar.setFirstDayOfWeek(Qt.Monday)
        self.calendar.setGridVisible(True)
        self.calendar.setMinimumDate(QDate.currentDate())
        self.calendar.showToday()
        if date_range:
            self.calendar.setDateRange(*date_range)

        buttonApplyDialog = QPushButton(self.tr('Apply'))
        buttonCancelDialog = QPushButton(self.tr('Cancel'))

        self.connect(buttonApplyDialog, SIGNAL('clicked()'),
                     self.applyDialog)
        self.connect(buttonCancelDialog, SIGNAL('clicked()'),
                     self, SLOT('reject()'))

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(buttonApplyDialog)
        buttonLayout.addWidget(buttonCancelDialog)

        self.desc = QLabel(desc)

        layout = QVBoxLayout()
        if desc:
            layout.addWidget(self.desc)
        layout.addWidget(self.calendar)
        layout.addLayout(buttonLayout)

        self.setLayout(layout)
        self.setWindowTitle(title)

    def setCallback(self, callback):
        self.callback = callback

    def applyDialog(self):
        """ Apply settings. """
        selected = self.calendar.selectedDate()
        if QMessageBox.Ok == self.callback(selected.toPyDate()):
            return
        self.accept()


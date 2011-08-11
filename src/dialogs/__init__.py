# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4 import uic

class BreakDialog(Exception):
    pass

class WizardDialog(QDialog):
    """ The dialog gives the description of a actions sequence and
    asks user for datas and process his replies."""

    ui_file = None # will define later
    params = None

    def __init__(self, parent=None, params=dict()):
        QDialog.__init__(self, parent)

        self.params = params

        dlg = uic.loadUi(self.ui_file, self)
        self.setupUi(dlg)

    def prefill(self, title):
        self.setWindowTitle(title)

    def setupUi(self, dialog):
        back_title = self.params.get('button_back', None)
        next_title = self.params.get('button_next', None)
        if back_title:
            dialog.goBack.setText(back_title)
        if next_title:
            dialog.goNext.setText(next_title)

        self.connect(dialog.goBack, SIGNAL('clicked()'), self.go_back)
        self.connect(dialog.goNext, SIGNAL('clicked()'), self.go_next)

    def go_back(self):
        self.reject()

    def go_next(self):
        print 'Next button pressed'

class WizardListDlg(WizardDialog):

    dialog = None
    ui_file = 'uis/dlg_list.ui'
    callback = None

    def __init__(self, parent=None, params=dict()):
        WizardDialog.__init__(self, parent, params)

    def prefill(self, title, data, callback):
        WizardDialog.prefill(self, title)
        self.callback = callback

        for id, text in data:
            item = QListWidgetItem(text, self.listWidget)
            item.setData(Qt.UserRole, QVariant(id))

    def setupUi(self, dialog):
        self.dialog = dialog
        WizardDialog.setupUi(self, self)
        self.connect(self.dialog.listWidget,
                     SIGNAL('itemDoubleClicked(QListWidgetItem *)'),
                     self.go_next)

    def go_next(self):
        list_widget = self.dialog.listWidget
        item = list_widget.currentItem()
        result = item.data(Qt.UserRole).toPyObject()
        self.callback(result)
        self.accept()

class WizardSpinDlg(WizardDialog):

    dialog = None
    ui_file = 'uis/dlg_spin.ui'
    callback = None
    SPIN_STEP = 4

    def __init__(self, parent=None, params=dict()):
        WizardDialog.__init__(self, parent, params)

    def prefill(self, title, data, callback):
        WizardDialog.prefill(self, title)
        self.callback = callback

        self.spinBox.setValue(data)

    def setupUi(self, dialog):
        self.dialog = dialog
        WizardDialog.setupUi(self, self)

        self.dialog.spinBox.setRange(4, 1000000)
        self.dialog.spinBox.setSingleStep(self.SPIN_STEP)
        self.connect(self.dialog.spinBox, SIGNAL('editingFinished()'), self.editing_finished)

    def go_next(self):
        spin_widget = self.dialog.spinBox
        result = spin_widget.value()
        self.callback(result)
        self.accept()

    def editing_finished(self):
        """
        Обработчик сигнала editingFinished(). Обеспечивает проверку
        введённого значения, которое должно быть кратно 8.
        """
        value = self.dialog.spinBox.value()
        if value <= self.SPIN_STEP:
            self.dialog.spinBox.setValue(self.SPIN_STEP)
        else:
            reminder = value % (2 * self.SPIN_STEP)
            if reminder != 0:
                self.dialog.spinBox.setValue(value - reminder)

class WizardPriceDlg(WizardDialog):

    dialog = None
    ui_file = 'uis/dlg_price.ui'
    callback = None

    def __init__(self, parent=None, params=dict()):
        WizardDialog.__init__(self, parent, params)

    def prefill(self, title, data, callback):
        WizardDialog.prefill(self, title)
        self.callback = callback

        self.doubleSpinBox.setValue(data)

    def setupUi(self, dialog):
        self.dialog = dialog
        WizardDialog.setupUi(self, self)
        self.dialog.doubleSpinBox.setMaximum(1000000)
        desc = self.params.get('desc')
        if desc is None:
            desc = '---'
        self.labelDesc.setText(desc)

    def go_next(self):
        spin_widget = self.dialog.doubleSpinBox
        result = spin_widget.value()
        self.callback(result)
        self.accept()

class PaymentDlg(WizardDialog):

    dialog = None
    ui_file = 'uis/dlg_price.ui'
    callback = None

    def __init__(self, parent=None, params=dict()):
        WizardDialog.__init__(self, parent, params)

    def setupUi(self, dialog):
        self.dialog = dialog
        WizardDialog.setupUi(self, self)

        self.callback = self.params.get('callback', None)
        initial_value = self.params.get('initial_value', 0)
        dialog_title = self.params.get('title', self.tr('Unknown'))
        self.doubleSpinBox.setRange(0, initial_value)
        self.doubleSpinBox.setValue(initial_value)
        WizardDialog.prefill(self, dialog_title)

    def go_next(self):
        value = self.doubleSpinBox.value()
        self.callback(value)
        self.accept()


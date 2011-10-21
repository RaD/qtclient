# -*- coding: utf-8 -*-
# (c) 2010 Ruslan Popov <ruslan.popov@gmail.com>

from settings import DEBUG
from ui_dialog import UiDlgTemplate

from PyQt4.QtGui import *
from PyQt4.QtCore import *

class DlgLogin(UiDlgTemplate):

    ui_file = 'uis/dlg_login.ui'

    def __init__(self, parent=None, **kwargs):
        self.connecting_to = kwargs.get('connecting_to')
        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        if self.connecting_to:
            self.editConnecting.setText(self.connecting_to)

        self.connect(self.buttonOk, SIGNAL('clicked()'),
                     self.applyDialog)
        self.connect(self.buttonCancel, SIGNAL('clicked()'),
                     self, SLOT('reject()'))

    def setCallback(self, callback):
        self.callback = callback

    def applyDialog(self):
        if self.callback:
            result = {'login': self.editLogin.text(),
                      'password': self.editPassword.text()}
            self.callback(result)
            self.accept()
        else:
            if DEBUG:
                print '[DlgLogin::applyDialog]: Check callback!'
            self.reject()

# -*- coding: utf-8 -*-
# (c) 2010-2012 Ruslan Popov <ruslan.popov@gmail.com>

from settings import DEBUG
from ui_dialog import UiDlgTemplate

from PyQt4.QtGui import *
from PyQt4.QtCore import *

from library import ParamStorage
from http import RequestFailedException

class DlgLogin(UiDlgTemplate):

    ui_file = 'uis/dlg_login.ui'
    params = ParamStorage()
    error_msg = None
    response = None

    def __init__(self, parent=None, **kwargs):
        self.stream = self.params.http
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
        login = self.editLogin.text()
        password=self.editPassword.text()
        data = dict(login=login, password=password)
        try:
            self.exchange(data)
        except RequestFailedException:
            self.reject()
        else:
            self.accept()

    def exchange(self, data):
        data = dict(data, version='.'.join(map(str, self.params.version)))
        if not self.stream.request('/api/login/', 'POST', credentials=data):
            self.error_msg = self.tr('Unable to make request: %1').arg(self.stream.error_msg)
            raise RequestFailedException()
        self.response = self.stream.piston()

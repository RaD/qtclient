# -*- coding: utf-8 -*-
# (c) 2009-2010 Ruslan Popov <ruslan.popov@gmail.com>

from settings import userRoles
from library import ParamStorage
from ui_dialog import UiDlgTemplate

from PyQt4.QtGui import *
from PyQt4.QtCore import *

GET_ID_ROLE = userRoles['getObjectID']

class Searching(UiDlgTemplate):
    """
    Класс реализует диалог поиска клиента по имени.

    Информация о подходящих клиентах/арендаторах приходит в ответ на
    запрос /api/<mode>/<name>/, где mode - режим (client или renter),
    а name - полное имя или фамилия.

    Пользователь выбирает из списка найденных людей одну запись,
    информация о которой передаётся в модуль manager.
    """
    ui_file = 'uis/dlg_searching.ui'
    params = ParamStorage()
    title = None
    mode = None

    def __init__(self, parent, *args, **kwargs):

        self.mode = kwargs.get('mode', 'client')
        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        self.tableUsers.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.buttonApply.setText(self.tr('Show'))
        self.buttonApply.setDisabled(True)

        self.connect(self.buttonSearch, SIGNAL('clicked()'), self.searchFor)
        self.connect(self.buttonApply, SIGNAL('clicked()'), self.applyDialog)
        self.connect(self.buttonClose,  SIGNAL('clicked()'), self, SLOT('reject()'))

    def setCallback(self, callback):
        self.callback = callback

    def searchFor(self):
        name = self.editSearch.text().toUtf8()
        http = self.params.http
        if not http.request('/api/%s/%s/' % (self.mode, name), 'GET', force=True):
            QMessageBox.critical(self, self.tr('Searching'), self.tr('Unable to search: %s') % http.error_msg)
            return
        response = http.parse()
        self.showList(response)
        self.buttonApply.setDisabled(False)

    def showList(self, user_list):
        while self.tableUsers.rowCount() > 0:
            self.tableUsers.removeRow(0)

        self.user_list = {}

        for index, user in enumerate(user_list):
            self.user_list[index] = user
            lastRow = self.tableUsers.rowCount()
            self.tableUsers.insertRow(lastRow)
            name = QTableWidgetItem(user['last_name']) # data may assign on cells only, use first one
            name.setData(GET_ID_ROLE, index)
            self.tableUsers.setItem(lastRow, 0, name)
            self.tableUsers.setItem(lastRow, 1, QTableWidgetItem(user['first_name']))
            self.tableUsers.setItem(lastRow, 2, QTableWidgetItem(user['email']))

        if len(user_list) > 0:
            self.tableUsers.selectRow(0)
            self.buttonSearch.setDisabled(False)
            self.buttonApply.setFocus(Qt.OtherFocusReason)
        else:
            self.buttonApply.setDisabled(True)
            self.buttonSearch.setFocus(Qt.OtherFocusReason)

    def applyDialog(self):
        index = self.tableUsers.currentIndex()
        selected_user = self.user_list[index.row()]
        self.callback(selected_user)
        self.accept()

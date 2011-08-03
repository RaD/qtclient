# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from settings import _, userRoles
from ui_dialog import UiDlgTemplate
from library import ParamStorage

from PyQt4.QtGui import *
from PyQt4.QtCore import *

GET_ID_ROLE = userRoles['getObjectID']

class ShowCoaches(UiDlgTemplate):

    """ Класс для отображения диалога со списком
    преподавателей. Используется при замене преподавателей для
    занятия."""

    ui_file = 'uis/dlg_event_coaches.ui'
    params = ParamStorage()
    title = _('Registered visitors')
    callback = None
    event = None

    def __init__(self, parent, *args, **kwargs):
        UiDlgTemplate.__init__(self, parent)

        self.callback = kwargs.get('callback')

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        self.tableCoaches.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.connect(self.buttonApply, SIGNAL('clicked()'), self.apply)
        self.connect(self.buttonClose,  SIGNAL('clicked()'), self, SLOT('reject()'))

    def initData(self, event, coaches_list):
        self.event = event

        # отображаем преподавателей
        for coach in coaches_list:
            rfid_code = coach.get('rfid')
            if not rfid_code:
                rfid_code = '--'
            lastRow = self.tableCoaches.rowCount()
            self.tableCoaches.insertRow(lastRow)
            name = QTableWidgetItem(coach.get('last_name'))
            # используем первую ячейку для хранения данных
            name.setData(GET_ID_ROLE, coach.get('uuid'))
            self.tableCoaches.setItem(lastRow, 0, name)
            self.tableCoaches.setItem(lastRow, 1, QTableWidgetItem(coach.get('first_name')))
            self.tableCoaches.setItem(lastRow, 2, QTableWidgetItem(rfid_code))
            self.tableCoaches.setItem(lastRow, 3, QTableWidgetItem(coach.get('registered')))

    def apply(self):
        selected = self.tableCoaches.selectionModel().selectedRows()
        if len(selected) > 3:
            message = _('Select no more three coaches.')
        else:
            uuid_list = [unicode(i.model().data(i, GET_ID_ROLE).toString()) for i in selected]
            if len(uuid_list) == 0:
                message = _('No selection, skip...')
            else:
                http = self.params.http
                params = [('action', 'CHANGE_COACH'), ('uuid', self.event.uuid),]
                params += [('leaders', i) for i in uuid_list]
                if not http.request('/api/history/', 'PUT', params):
                    QMessageBox.critical(self, _('Register change'),
                                         _('Unable to register: %s') % http.error_msg)
                    return
                status, response = http.piston()
                if 'ALL_OK' == status:
                    self.accept()
                    self.callback(uuid_list)
                    return
                else:
                    message = _('Unable to exchange.')
        QMessageBox.warning(self, _('Coaches exchange'), message)

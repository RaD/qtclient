# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from settings import userRoles
from ui_dialog import UiDlgTemplate
from library import ParamStorage

from PyQt4.QtGui import *
from PyQt4.QtCore import *

GET_ID_ROLE = userRoles['getObjectID']

class ShowVisitors(UiDlgTemplate):

    ui_file = 'uis/dlg_event_visitors.ui'
    params = ParamStorage()
    event_uuid = None

    def __init__(self, parent=None):
        self.stream = self.params.http
        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        self.tableVisitors.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableVisitors.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableVisitors.customContextMenuRequested.connect(self.context_menu)

        self.connect(self.buttonClose, SIGNAL('clicked()'), self, SLOT('reject()'))


    def initData(self, event_uuid):
        self.event_uuid = event_uuid
        if not self.stream.request('/api/history/%s/' % self.event_uuid, 'GET', force=True):
            msg = self.tr('Unable to fetch: %s') % http.error_msg
            QMessageBox.critical(self, self.tr('Visitors'), msg)
            return

        status, data = self.stream.piston()
        if 'ALL_OK' == status:
            for item in data.get('visit_set', []):
                client = item['voucher']['client']

                last_name = client.get('last_name')
                first_name = client.get('first_name')
                registered = item.get('registered')
                rfid_code = client.get('rfid')
                if rfid_code is None:
                    rfid_code = '--'

                lastRow = self.tableVisitors.rowCount()
                self.tableVisitors.insertRow(lastRow)
                name = QTableWidgetItem(last_name)
                # data may assign on cells only, use first one
                name.setData(GET_ID_ROLE, self.event_uuid)
                self.tableVisitors.setItem(lastRow, 0, name)
                self.tableVisitors.setItem(lastRow, 1, QTableWidgetItem(first_name))
                self.tableVisitors.setItem(lastRow, 2, QTableWidgetItem(rfid_code))
                self.tableVisitors.setItem(lastRow, 3, QTableWidgetItem(registered))

    def context_menu(self, position):
        """ Create context menu."""
        menu = QMenu()
        action_reprint = menu.addAction(self.tr('Reprint Selected'))
        action_cancel = menu.addAction(self.tr('Cancel Selected'))
        action = menu.exec_(self.tableVisitors.mapToGlobal(position))

        # choose action
        if action == action_reprint:
            self.reprint()
        elif action == action_cancel:
            QMessageBox.warning(self, self.tr('Warning'),
                                self.tr('Not yet implemented!'))
        else:
            print '%s: %s' % (self.__class__, self.tr('Unknown context menu action'))

    def reprint(self):
        selected = self.tableVisitors.selectionModel().selectedRows()
        for index in selected:
            model = index.model()
            visit_id, ok = model.data(index, GET_ID_ROLE).toInt()
            if ok:
                print_this = self.get_visit_info(visit_id)
                self.parent.parent.printer.hardcopy(print_this)

    def get_visit_info(self, visit_id):
        if not self.http.request('/manager/reprint_visit/', {'item_id': visit_id}):
            QMessageBox.critical(self, self.tr('Visit Reprint'), self.tr('Unable to fetch: %s') % self.http.error_msg)
            return
        default_response = None
        response = self.http.parse(default_response)
        if response and response.get('code', None) == 200 and 'print_this' in response:
            return response['print_this']
        print 'log this'

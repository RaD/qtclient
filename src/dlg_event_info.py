# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

import time
from datetime import datetime

from settings import _, DEBUG
from event_storage import Event
from ui_dialog import UiDlgTemplate
from dialogs import WizardListDlg
from dialogs.rfid_wait import WaitingRFID
from dialogs.show_coaches import ShowCoaches
from dialogs.searching import Searching
from dlg_show_visitors import ShowVisitors

__ = lambda x: datetime(*time.strptime(str(x), '%Y-%m-%d %H:%M:%S')[:6])

from PyQt4.QtGui import *
from PyQt4.QtCore import *

ERR_EVENT_NOVOUCHERLIST1 = 2201
ERR_EVENT_NOVOUCHERLIST2 = 2202
ERR_EVENT_REGISTERVISIT = 2203

EVENT_TYPE_TEAM = '1'
EVENT_TYPE_RENT = '2'

def dump(value):
    import pprint
    pprint.pprint(value)

class EventInfo(UiDlgTemplate):

    ui_file = 'uis/dlg_event_info.ui'
    title = _('Event\'s information')
    schedule = None # кэшируем здесь данные от сервера
    all_coaches = None # кэш с данными о преподавателях

    def __init__(self, parent=None, params=dict()):
        UiDlgTemplate.__init__(self, parent, params)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        self.connect(self.buttonClose,       SIGNAL('clicked()'), self.close)
        self.connect(self.buttonVisitors,    SIGNAL('clicked()'), self.showVisitors)
        self.connect(self.buttonVisitRFID,   SIGNAL('clicked()'), self.search_by_rfid)
        self.connect(self.buttonVisitManual, SIGNAL('clicked()'), self.search_by_name)
        self.connect(self.buttonRemove,      SIGNAL('clicked()'), self.removeEvent)
        self.connect(self.buttonFix,         SIGNAL('clicked()'), self.fixEvent)
        self.connect(self.buttonChange,      SIGNAL('clicked()'), self.changeCoaches)
        self.connect(self.comboFix, SIGNAL('currentIndexChanged(int)'),
                     lambda: self.buttonFix.setDisabled(False))

    def initData(self, obj, index):
        """ Use this method to initialize the dialog. """
        self.schedule_object = obj
        self.schedule_index = index

        title =  _('Event info')

        # если данных в кэше нет, то получаем их от сервера
        if self.schedule is None:
            # получаем информацию о активности
            if not self.http.request('/manager/get_one/',
                                     {'action': 'get_event_info',
                                      'item_id': self.schedule_object.id}):
                QMessageBox.critical(self, title,
                                     _('Unable to fetch: %s') % self.http.error_msg)
                return
            default_response = None
            response = self.http.parse(default_response)
            if not(response and 'data' in response):
                QMessageBox.critical(self, title,
                                     _('Unable to parse: %s') % self.http.error_msg)
                return
            # сохраняем данные в кэше
            self.schedule = response['data']

        event = self.schedule['event']
        status = self.schedule.get('status', 0) # 0 means wainting
        room = self.schedule['room']
        self.editStyle.setText(event.get('dance_styles', _('Rent')))
        self.editPriceCategory.setText( event['category']['title'] )

        if self.schedule.get('type', None) == EVENT_TYPE_TEAM:
            # get coaches list from schedule, not from team, because of exchange
            self.editCoaches.setText(self.schedule.get('coaches', _('Unknown')))

        begin = __(self.schedule['begin_datetime'])
        end = __(self.schedule['end_datetime'])
        self.editBegin.setDateTime(QDateTime(begin))
        self.editEnd.setDateTime(QDateTime(end))

        current_id = int(room['id'])
        self.current_room_index = current_id - 1
        for title, color, room_id in self.parent.rooms:
            self.comboRoom.addItem(title, QVariant(room_id))
            if room_id == current_id + 100:
                current = self.comboRoom.count() - 1
        self.comboRoom.setCurrentIndex(self.current_room_index)

        # disable controls for events in the past
        is_past = begin < datetime.now()
        self.buttonRemove.setDisabled(is_past)
        self.buttonVisitRFID.setDisabled(is_past)
        self.buttonVisitManual.setDisabled(is_past)
        self.buttonChange.setDisabled(is_past)

        self._init_fix(status)

    def _init_fix(self, current):
        """ Helper method to init eventFix combo."""
        for id, title in self.parent.static['event_fix_choice']:
            self.comboFix.addItem(title, QVariant(id))
        self.comboFix.setCurrentIndex(int(current))
        self.buttonFix.setDisabled(True)

    def showVisitors(self):
        dialog = ShowVisitors(self, {'http': self.http})
        dialog.setModal(True)
        dialog.initData(self.schedule['id'])
        dialog.exec_()

    def search_by_rfid(self):
        """ Поиск пользователя по RFID и получение списка карт,
        соответствующих событию."""

        def callback(rfid):
            self.user_id = 'rfid:%s' % rfid

        # диалог rfid считывателя
        params = {'http': self.http, 'callback': callback,}
        dialog = WaitingRFID(self, params)
        dialog.setModal(True)
        dlgStatus = dialog.exec_()

        if QDialog.Accepted == dlgStatus:
            self.visit_register(self.user_id)

    def search_by_name(self):
        """ Поиск пользователя по его имени и получение списка карт,
        соответствующих событию."""

        def callback(user):
            self.user_id = user['id']

        params = {'http': self.http, 'static': self.parent.static,
                  'mode': 'client', 'apply_title': _('Register'),}
        self.dialog = Searching(self, params)
        self.dialog.setModal(True)
        self.dialog.setCallback(callback)
        dlgStatus = self.dialog.exec_()

        if QDialog.Accepted == dlgStatus:
            self.visit_register(self.user_id)

    def visit_register(self, user_id):
        schedule_id = self.schedule.get('id', 0)
        title = _('Client Registration')
        # получаем список подходящих ваучеров
        params = {'user_id': user_id, 'schedule_id': schedule_id}
        if not self.http.request('/manager/voucher_list_by_schedule/', params):
            QMessageBox.warning(self, title, '%s: %i\n\n%s\n\n%s' % (
                _('Error'), ERR_EVENT_NOVOUCHERLIST1,
                _('Unable to fetch the list of vouchers: %s') % self.http.error_msg,
                _('Call support team!')))
            return
        default_response = None
        response = self.http.parse(default_response)
        if response and 'voucher_list' in response:
            voucher_list = response['voucher_list'] # есть список
            if voucher_list == []: # пустой список
                QMessageBox.information(self, _('Client Registration'),
                                        _('No voucher for this visit.\n\nBuy one.'))
                return
        else:
            # иначе сообщаем о проблеме
            QMessageBox.critical(self, title, '%s: %i\n\n%s\n\n%s' % (
                _('Error'), ERR_EVENT_NOVOUCHERLIST2,
                _('Server did not send the list of vouchers.'),
                _('Call support team!')))
            return

        # показываем список менеджеру, пусть выбирает
        def callback(voucher_id):
            self.voucher_id = voucher_id

        dialog = WizardListDlg(params={'button_back': _('Cancel'), 'button_next': _('Ok')})
        dialog.setModal(True)

        # подготавливаем список подходящих ваучеров
        prepared_list = []
        for v in voucher_list:
            v_id = v['id']
            if v['voucher_type'] in ('abonement',):
                v_title = '%s - %s' % (v['voucher_title'],
                                       v['category']['title'])
            else:
                v_title = v['voucher_title']
            prepared_list.append( (v_id, v_title) )
        dialog.prefill(_('Choose the Voucher'), prepared_list, callback)
        if QDialog.Accepted == dialog.exec_():
            title = _('Register visit')
            # регистрируем клиента на событие
            params = {'schedule_id': schedule_id, 'voucher_id': self.voucher_id}
            if not self.http.request('/manager/register_visit/', params):
                # иначе сообщаем о проблеме
                QMessageBox.critical(self, title, '%s: %i\n\n%s\n\n%s' % (
                    _('Error'), ERR_EVENT_REGISTERVISIT,
                    _('Unable to register: %s') % self.http.error_msg,
                    _('Call support team!')))
                return
            default_response = None
            response = self.http.parse(default_response)
            if response:
                message = _('The client is registered on this event.')
                self.parent.printer.hardcopy(response['print_this'])
            else:
                error_msg = self.http.error_msg
                message = _('Unable to register the visit!\nReason:\n%s') % error_msg
            QMessageBox.information(self, title, message)


    def changeRoom(self, new_index):
        # Room change:
        # 1. The choosen room is empty inside whole time period.
        #    Change a room for the event.
        # 2. The choosen room is busy at all, i.e. two event are equal in time.
        #    Change the rooms.
        # 3. The choosen room is busy partially.
        #    Cancel the change, raise message.
        if new_index != self.current_room_index:
            # make room checking
            #
            pass

    def removeEvent(self):
        reply = QMessageBox.question(
            self, _('Event remove'),
            _('Are you sure to remove this event from the calendar?'),
            QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.Yes:
            params = {'id': self.schedule['id']}
            if not self.http.request('/manager/cal_event_del/', params):
                QMessageBox.critical(self, _('Event deletion'), _('Unable to delete: %s') % self.http.error_msg)
                return
            default_response = None
            response = self.http.parse(default_response)
            if response:
                index = self.comboRoom.currentIndex()
                room_id, ok = self.comboRoom.itemData(index).toInt()
                model = self.parent.schedule.model()
                model.remove(self.schedule_object, self.schedule_index, True)
                QMessageBox.information(self, _('Event removing'),
                                        _('Complete.'))
                self.accept()
            else:
                QMessageBox.information(self, _('Event removing'),
                                        _('Unable to remove this event!'))

    def fixEvent(self):
        index = self.comboFix.currentIndex()
        fix_id, ok = self.comboFix.itemData(index).toInt()

        params = {'event_id': self.schedule['id'],
                  'fix_id': fix_id}
        if not self.http.request('/manager/register_fix/', params):
            QMessageBox.critical(self, _('Register fix'), _('Unable to fix: %s') % self.http.error_msg)
            return
        default_response = None
        response = self.http.parse(default_response)
        if response:
            message = _('The event has been fixed.')

            self.schedule_object.set_fixed(fix_id)
            model = self.parent.schedule.model()
            model.change(self.schedule_object, self.schedule_index)
            self.buttonFix.setDisabled(True)
        else:
            message = _('Unable to fix this event.')
        QMessageBox.information(self, _('Event fix registration'), message)

    def changeCoaches(self):
        """ Метод реализует функционал замены преподавателей для события. """
        # если данных в кэше нет, то получаем их от сервера
        if self.all_coaches is None:
            # получаем информацию о преподавателях
            title = _('Coaches')
            if not self.http.request('/manager/get_all/',
                                     {'action': 'coaches',}):
                QMessageBox.critical(self, title,
                                     _('Unable to fetch: %s') % self.http.error_msg)
                return
            default_response = None
            response = self.http.parse(default_response)
            if not (response and 'data' in response):
                QMessageBox.critical(self, title,
                                     _('Unable to fetch: %s') % self.http.error_msg)
                return
            # сохраняем данные в кэше
            self.all_coaches = response['data']

        def coaches_callback(coach_id_list):
            from library import filter_dictlist
            # get the coach descriptions' list using its id list
            coaches_dictlist = filter_dictlist(self.parent.static['coaches'], 'id', coach_id_list)
            self.schedule_object.set_coaches(coaches_dictlist)

        dialog = ShowCoaches(self, {'http': self.http})
        dialog.setCallback(coaches_callback)
        dialog.setModal(True)
        dialog.initData(self.schedule, self.all_coaches)
        dialog.exec_()

        # очищаем кэш и заново запрашиваем информацию о событии, чтобы
        # показать изменения списка преподавателей.
        self.schedule = None
        self.initData(self.schedule_object, self.schedule_index)

        # update schedule model to immediate refresh this event
        model = self.parent.schedule.model()
        model.change(self.schedule_object, self.schedule_index)

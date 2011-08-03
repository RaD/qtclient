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

from library import ParamStorage

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
    s_obj = None
    s_idx = None

    def __init__(self, parent=None):
        UiDlgTemplate.__init__(self, parent)
        self.params = ParamStorage()

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
        self.s_obj = obj
        self.s_idx = index

        title =  _('Event info')

        self.editStyle.setText(self.s_obj.styles)
        self.editPriceCategory.setText(self.s_obj.category)
        self.editCoaches.setText(self.s_obj.coaches)

        begin = self.s_obj.begin
        end = self.s_obj.end
        self.editBegin.setDateTime(QDateTime(begin))
        self.editEnd.setDateTime(QDateTime(end))

        for index, room in self.params.static.get('rooms_by_index').items():
            self.comboRoom.addItem(room.get('title'), QVariant(index))

        self.comboRoom.setCurrentIndex(self.params.static.get('rooms_by_uuid').get(self.s_obj.room_uuid))

        # disable controls for events in the past
        is_past = begin < datetime.now()
        self.buttonRemove.setDisabled(is_past or self.s_obj.prototype == self.s_obj.RENT)
        self.buttonVisitRFID.setDisabled(is_past or self.s_obj.prototype == self.s_obj.RENT)
        self.buttonVisitManual.setDisabled(is_past or self.s_obj.prototype == self.s_obj.RENT)
        self.buttonChange.setDisabled(is_past or self.s_obj.prototype == self.s_obj.RENT)
        self.buttonVisitors.setDisabled(self.s_obj.prototype == self.s_obj.RENT)

        #self._init_fix(status)

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
            self.rfid_id = rfid

        # диалог rfid считывателя
        dialog = WaitingRFID(self, callback=callback)
        dialog.setModal(True)
        if QDialog.Accepted == dialog.exec_():
            http = self.params.http
            if not http.request('/api/client/%s/' % self.rfid_id, 'GET', force=True):
                QMessageBox.critical(self, _('Client info'), _('Unable to fetch: %s') % http.error_msg)
                return
            response = http.parse()

            if 0 == len(response):
                QMessageBox.warning(self, _('Warning'), _('This RFID belongs to nobody.'))
                return False
            else:
                self.last_user_uuid = response[0].get('uuid')
                return self.visit_register(self.last_user_uuid)

    def search_by_name(self):
        """ Поиск пользователя по его имени и получение списка карт,
        соответствующих событию."""

        def callback(user):
            self.user_id = user['id']

        self.dialog = Searching(self, mode='client', apply_title=_('Register'))
        self.dialog.setModal(True)
        self.dialog.setCallback(callback)
        if QDialog.Accepted == self.dialog.exec_():
            self.visit_register(self.user_id)

    def select_voucher_list(self, *args, **kwargs):
        # получаем список подходящих ваучеров
        http = self.params.http
        if not http.request('/api/voucher/%(event_id)s/%(client_id)s/%(start)s/' % kwargs, 'GET', force=True):
            return None
        status, response = http.piston()
        return u'ALL_OK' == status and response or None

    def visit_register(self, user_uuid):
        title = _('Client Registration')
        event = self.s_obj
        # получаем список подходящих ваучеров
        voucher_list = self.select_voucher_list(client_id=user_uuid, event_id=event.uuid,
                                                start=event.begin.strftime('%Y%m%d%H%M%S'))
        if not voucher_list or 0 == len(voucher_list):
            QMessageBox.information(self, title,
                                    _('No voucher for this visit.\n\nBuy one.'))
            return False

        # показываем список менеджеру, пусть выбирает
        def callback(voucher_uuid):
            self.voucher_uuid = voucher_uuid
        def make_title(voucher):
            out = []
            card = voucher.get('_card_cache')
            if card:
                out.append( card.get('title') )
            category = voucher.get('_category_cache')
            if category:
                out.append( category.get('title') )
            return ' - '.join(out)

        dialog = WizardListDlg(params={'button_back': _('Cancel'), 'button_next': _('Ok')})
        dialog.setModal(True)
        dialog.prefill(_('Choose the Voucher'),
                       [(v['uuid'], make_title(v)) for v in voucher_list],
                       callback)
        # ваучер выбран, регистрируем посещение
        if QDialog.Accepted == dialog.exec_():
            http = self.params.http
            if not http.request('/api/voucher/', 'PUT',
                                {'action': 'VISIT',
                                 'uuid': self.voucher_uuid,
                                 'plan_uuid': event.uuid,
                                 'room_uuid': event.room_uuid,
                                 'day': event.begin.strftime('%Y%m%d')}):
                QMessageBox.warning(self, title, '%s: %i\n\n%s\n\n%s' % (
                    _('Error'), ERR_EVENT_REGISTERVISIT,
                    _('Unable to register the visit: %s') % http.error_msg,
                    _('Call support team!')))
                return False
            status, response = http.piston()
            print status, response
            if u'CREATED' == status:
                QMessageBox.information(self, title,
                                        _('The client has been registered for this event.'))
                # PRINT CHECK HERE
                return True
            else:
                QMessageBox.warning(self, title,
                                    _('Unable to register!\nStatus: %s') % status)
        return False

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
                model.remove(self.s_obj, self.s_idx, True)
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

            self.s_obj.set_fixed(fix_id)
            model = self.parent.schedule.model()
            model.change(self.s_obj, self.s_idx)
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
            self.s_obj.set_coaches(coaches_dictlist)

        dialog = ShowCoaches(self, {'http': self.http})
        dialog.setCallback(coaches_callback)
        dialog.setModal(True)
        dialog.initData(self.schedule, self.all_coaches)
        dialog.exec_()

        # очищаем кэш и заново запрашиваем информацию о событии, чтобы
        # показать изменения списка преподавателей.
        self.schedule = None
        self.initData(self.s_obj, self.s_idx)

        # update schedule model to immediate refresh this event
        model = self.parent.schedule.model()
        model.change(self.s_obj, self.s_idx)

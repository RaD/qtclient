# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from settings import _, DEBUG, userRoles

from dialogs import BreakDialog, WizardDialog, WizardListDlg, WizardSpinDlg, WizardPriceDlg, PaymentDlg
from dialogs.rfid_wait import WaitingRFID

#from model_sorting import SortClientTeams
from card_list import CardListModel
from rent_list import RentListModel
from dialogs.assign_rent import AssignRent
from settings import _, userRoles
from ui_dialog import UiDlgTemplate
from library import dictlist2dict, filter_dictlist, ParamStorage
from http import HttpException

from datetime import datetime, date, timedelta

import json

from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4 import uic

ERR_VOUCHER_PAYMENT = 2101

def str2date(value):
    return datetime.strptime(value, '%Y-%m-%d').date()

class ClientInfo(UiDlgTemplate):

    ui_file = 'uis/dlg_user_info.ui'
    params = ParamStorage()
    title = _('Client\'s information')
    card_model = None
    user_id = None # новые записи обозначаются отсутствием идентификатора
    discounts_by_index = {}
    discounts_by_uuid = {}
    rfid_id = None
    rfid_uuid = None
    changed = False

    def __init__(self, parent=None):
        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        self.tableHistory.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.card_model = CardListModel(self)
        self.tableHistory.setModel(self.card_model)
        self.tableHistory.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableHistory.customContextMenuRequested.connect(self.context_menu)

        # добавляем на диалог все зарегистрированные виды скидок
        for index, item in enumerate(self.params.static.get('discount_client')):
            checkbox = QCheckBox('%(title)s (%(percent)s%%)' % item)
            self.discounts_by_index[index] = (checkbox, item)
            self.discounts_by_uuid[item.get('uuid')] = (checkbox, item)
            self.discountLayout.addWidget(checkbox)
        self.discountLayout.addStretch(10)

        self.connect(self.buttonAssign, SIGNAL('clicked()'), self.assign_voucher)
        self.connect(self.buttonRFID,   SIGNAL('clicked()'), self.assignRFID)
        self.connect(self.buttonApply,  SIGNAL('clicked()'), self.applyDialog)
        self.connect(self.buttonClose,  SIGNAL('clicked()'), self, SLOT('reject()'))

    def context_menu(self, position):
        """ Create context menu."""

        index = self.tableHistory.indexAt(position)
        model = index.model()
        menu = QMenu()
        is_debt, debt_amount = model.is_debt_exist(index, True)
        cancelled = model.is_cancelled(index)
        may_prolongate = model.may_prolongate(index)

        action_payment_add = menu.addAction(_('Payment'))
        action_payment_add.setDisabled(not is_debt)
        action_prolongate = menu.addAction(_('Prolongate'))
        action_prolongate.setDisabled(not(cancelled and may_prolongate and not is_debt))
        action_cancel = menu.addAction(_('Cancel'))
        action_cancel.setDisabled(cancelled)
        action = menu.exec_(self.tableHistory.mapToGlobal(position))

        # choose action
        if action == action_payment_add:
            self.voucher_payment_add(index, debt_amount)
        elif action == action_prolongate:
            self.voucher_prolongate(index)
        elif action == action_cancel:
            self.voucher_cancel(index)
        else:
            print 'unknown'

    def initData(self, data={}):
        self.user_id = data.get('uuid')

        # Определение подсказок
        meta = [('last_name', self.editLastName),
                ('first_name', self.editFirstName),
                ('email', self.editEmail),
                ('phone', self.editPhone),
                ]
        for key, obj in meta:
            text = data.get(key, '')
            obj.setText(text)
            obj.setToolTip(text)

        for item in data.get('discount'):
            checkbox, desc = self.discounts_by_uuid[item.get('uuid')]
            checkbox.setCheckState(Qt.Checked)

        birth_date = data.get('birth_date', None) # it could be none while testing
        self.dateBirth.setDate(birth_date and str2date(birth_date) or \
                               QDate.currentDate())

        rfid = data.get('rfid')
        if rfid:
            self.rfid_uuid = rfid.get('uuid')
            self.rfid_code = rfid.get('code')

            self.buttonRFID.setText(self.rfid_code)
            self.buttonRFID.setToolTip(_('RFID code of this client.'))
            self.buttonRFID.setDisabled(True)

        # заполняем список приобретённых ваучеров
        self.tableHistory.model().init_data( data.get('voucher_list', []) )

    def voucher_payment_add(self, index, initial_value=0.00):
        """ Show price dialog and register payment. """
        title = _('Register payment')

        def callback(value):
            print 'callback value is', value
            self.payment = value

        params = {
            'title': _('Payment'),
            'button_back': _('Cancel'),
            'button_next': _('Apply'),
            'callback': callback,
            'initial_value': initial_value,
            }

        # получаем информацию о выбранном ваучере
        model = index.model()
        voucher = model.get_voucher_info(index)
        voucher_id = voucher.get('id', 0)

        # запрашиваем сумму доплаты
        dialog = PaymentDlg(self, params)
        dialog.setModal(True)

        if QDialog.Accepted == dialog.exec_():
            # проводим платёж
            params = {'voucher_id': voucher_id, 'amount': self.payment}
            if not self.http.request('/manager/payment_add/', params):
                QMessageBox.critical(self, title, _('Unable to register: %s') % self.http.error_msg)
                return
            default_response = None
            response = self.http.parse(default_response)
            if response and response.get('saved_id', 0) == voucher_id:
                # если платёж прошёл
                # приводим отображаемую модель к нужному виду
                if 'paid' in voucher:
                    voucher['paid'] += self.payment
                    voucher['count_available'] = self.calculate_available_visits(
                        voucher['price'], voucher['paid'], voucher['category']['once_price'], voucher['count_sold'])
            else:
                # иначе сообщаем о проблеме
                QMessageBox.warning(self, title, '%s: %i\n\n%s\n\n%s' % (
                    _('Error'), ERR_VOUCHER_PAYMENT,
                    _('Server could not receive that payment.'),
                    _('Call support team!')))

    def voucher_prolongate(self, index):
        """ Метод для пролонгации ваучера. Отображает диалог с
        календарём, позволяя продлить действие ваучера до двух недель
        от текущего дня."""
        from dlg_calendar import DlgCalendar
        title = _('Voucher Prolongation')
        # получаем информацию о ваучере
        model = index.model()
        voucher = model.get_voucher_info(index)
        voucher_id = voucher.get('id')
        if not voucher_id:
            raise Exception('Bad voucher id')
        # определяем обработчик диалога
        def callback(selected_date):
            self.selected_date = selected_date
        # отображаем диалог с календарём
        params = {'date_range': (date.today(), date.today() + timedelta(days=14)),
                  'title': title, 'desc': _('Choose the prolongation date:')}
        self.dialog = DlgCalendar(self, **params)
        self.dialog.setModal(True)
        self.dialog.setCallback(callback)
        if QDialog.Accepted == self.dialog.exec_():
            # выполняем пролонгацию на сервере
            params = {'voucher_id': voucher_id, 'prolongate_date': self.selected_date}
            if not self.http.request('/manager/voucher_prolongate/', params):
                QMessageBox.critical(self, title, _('Unable to prolongate: %s') % self.http.error_msg)
                return
            # проверяем результат
            default_response = None
            response = self.http.parse(default_response)
            if response and 'saved_id' in response:
                QMessageBox.information(self, title, _('Voucher has been prolongated sucessfully.'))
                # приводим отображаемую модель к нужному виду
                if 'end_date' in voucher:
                    voucher['end_date'] = self.selected_date
                    voucher['cancel_datetime'] = None
                    model.update(index)
            else:
                QMessageBox.critical(self, title, _('Could not prolongate this voucher!'))

    def voucher_cancel(self, index):
        """ Метод для отмены ваучера. Отображает форму "Да/Нет". """
        title = _('Voucher Cancellation')
        # получаем информацию о ваучере
        model = index.model()
        voucher = model.get_voucher_info(index)
        voucher_id = voucher.get('id')
        if not voucher_id:
            raise Exception('Bad voucher id')
        # удостоверяемся в трезвом уме пользователя
        if QMessageBox.Yes == QMessageBox.question(self, title,
                                                   _('Are you sure to cancel this voucher?'),
                                                   QMessageBox.Yes, QMessageBox.No):
            # отменяем ваучер
            if not self.http.request('/manager/get_one/',
                                     {'action': 'voucher_cancel', 'item_id': voucher_id}):
                QMessageBox.critical(self, title, _('Unable to cancel: %s') % self.http.error_msg)
                return
            default_response = None
            response = self.http.parse(default_response)
            if response and 'data' in response:
                QMessageBox.information(self, title, _('Voucher has been cancelled sucessfully.'))
                # приводим отображаемую модель к нужному виду
                if 'cancel_datetime' in voucher:
                    voucher['cancel_datetime'] = datetime.now()
                    model.update(index)
            else:
                QMessageBox.critical(self, title, _('Could not cancel this voucher!'))

    def assignRFID(self):
        def callback(rfid):
            self.rfid_code = rfid

        dialog = WaitingRFID(self, mode='client', callback=callback)
        dialog.setModal(True)
        dlgStatus = dialog.exec_()

        if QDialog.Accepted == dlgStatus:
            h = self.params.http
            if not h.request('/api/rfid/%s/' % self.rfid_code, 'POST'):
                QMessageBox.critical(self, _('Client info'), _('Unable to fetch: %s') % h.error_msg)
                return
            status, response = h.piston()
            if status == 'DUPLICATE_ENTRY':
                QMessageBox.warning(self, _('Warning'), _('This RFID is used already!'))
            elif status == 'CREATED':
                self.rfid_uuid = response.get('uuid')
                self.buttonRFID.setText(self.rfid_code)
                self.buttonRFID.setDisabled(True)

    def wizard_dialog(self, dtype, title, data_to_fill, desc=None):
        self.wizard_data = None

        def callback(data):
            self.wizard_data = data # id, title, voucher_type

        dialogs = {
            'list': WizardListDlg,
            'spin': WizardSpinDlg,
            'price': WizardPriceDlg,
            }

        params = {'button_back': _('Cancel'), 'desc': desc}
        dialog = dialogs[dtype](self, params)
        dialog.setModal(True)
        dialog.prefill(title, data_to_fill, callback)
        if QDialog.Accepted == dialog.exec_():
            return self.wizard_data
        else:
            raise BreakDialog('Dialog is not accepted')

    def calculate_available_visits(self, price, paid, once_price, count_sold):
        if float(price) - float(paid) < 0.01:
            # оплачена полная стоимость ваучера
            return int(count_sold)
        else:
            from math import floor
            return int(floor(paid / once_price))

    def possible_voucher_types(self):
        """ Метод для генерации списка возможных типов ваучера для
        первого диалога."""
        free_visit_used = self.tableHistory.model().free_visit_used
        card_list = []
        for i in self.params.static.get('card_ordinary'):
            if i['slug'] in ('flyer', 'test',) and free_visit_used:
                continue

            item = (i['slug'], i['title'])
            card_list.append(item)
        if 0 < len(self.params.static.get('card_club')):
            item = ('club', _('Club Card'))
            card_list.append(item)
        if 0 < len(self.params.static.get('card_promo')):
            item = ('promo', _('Promo Card'))
            card_list.append(item)
        return card_list

    def assign_voucher(self):
        """ Общий метод для добавления ваучера клиенту. Далее, в
        зависимости от выбора менеджера, происходит вызов нужного
        функционала."""

        try:
            voucher_type = self.wizard_dialog('list', _('Choose the voucher\'s type'),
                                              self.possible_voucher_types())
            voucher_type_str = str(voucher_type)

            if voucher_type_str in ('flyer', 'test', 'once', 'abonement'):
                steps = self.assign_ordinary(voucher_type_str)
            elif voucher_type_str == 'club':
                steps = self.assign_club()
            elif voucher_type_str == 'promo':
                steps = self.assign_promo()
            else:
                raise Exception(_('Error'))
        except BreakDialog:
            # диалог был просто закрыт, покупки нет
            pass
        else:
            model = self.tableHistory.model()
            model.insert_new(steps)

    def assign_ordinary(self, voucher_type):
        """ Метод для добавления ваучеров обычного типа. """
        steps = {'voucher_type': voucher_type}

        # выделяем нужный тип карт из списка обычных
        static_info = filter_dictlist(self.params.static.get('card_ordinary'), 'slug', voucher_type)[0]
        cat_list = [(i['id'], i['title']) for i in static_info['price_categories']]
        dis_list = [(i['id'], i['title']) for i in static_info['discounts']]
        cat_dict_id = {}
        dis_dict_id = {}
        for i in static_info['price_categories']:
            cat_dict_id.update( { i['id']: i } )
        for i in static_info['discounts']:
            dis_dict_id.update( { i['id']: i } )

        if voucher_type in ('flyer', 'test', 'once'):
            # эти типы ваучеров могут регистрироваться на текущий день только
            steps['begin_date'] = date.today()
            steps['end_date'] = date.today()
        elif voucher_type in ('abonement',):
            # эти типы ваучеров определяют время жизни от первого занятия
            steps['begin_date'] = None
            steps['end_date'] = None

        try:
            if voucher_type in ('once', 'abonement', 'club',):
                result = self.wizard_dialog('list', _('Price Category'), cat_list)
                if result:
                    steps['category'] = int(result)
            if voucher_type in ('test',):
                # назначаем самую дорогую из имеющихся категорий
                category = reduce(lambda a, b: int(a['full_price']) > int(b['full_price']) and a or b,
                                  static_info['price_categories'])
                steps['category'] = int(category['id'])

            if voucher_type == 'abonement':
                # количество посещений
                result = self.wizard_dialog('spin', _('Visit Count'), 8)
                if result:
                    steps['count_sold'] = int(result)

                # расчёт применяемых скидок, скидки назначаются с 8 посещений
                if steps['count_sold'] >= 8:
                    discount_percent = 0
                    discount_ids = []
                    # сначала проверяем клиентские скидки
                    for item_id, (obj, desc) in self.discounts.items():
                        if obj.checkState() == Qt.Checked:
                            discount_percent += int(desc.get('percent', 0))
                            discount_ids.append(item_id)
                    # потом проверяем скидку по количеству приобретённых посещений
                    tmp_id = 0
                    tmp_percent = 0
                    for discount in sorted(self.params.static.get('discount_card'),
                                           lambda a,b: cmp(int(a['threshold']), int(b['threshold']))):
                        if discount['threshold'] <= steps['count_sold']:
                            tmp_id = discount['id']
                            tmp_percent = discount['percent']
                        else:
                            break # заканчиваем цикл
                    if not tmp_id == 0:
                        discount_percent += int(tmp_percent)
                        discount_ids.append(int(tmp_id))

                steps['discount_percent'] = discount_percent
                steps['discount_ids'] = discount_ids

                self._price_abonement(steps) # высчитываем стоимость

                category = cat_dict_id.get(steps['category'])
                once_price = float(category.get('once_price', 0.00))
                price = float(steps.get('price', 0.00))
                discount_price = price - (price * discount_percent / 100)
                if discount_price < 2000.00:
                    discount_price = 2000.00
                steps['discount_price'] = discount_price

                while True:
                    result = float(self.wizard_dialog('price', _('Paid'), discount_price,
                                                      _('Payment range is %(min)0.2f .. %(max)0.2f.' ) % {
                                                          'min': once_price, 'max': discount_price
                                                          }))
                    if result >= once_price and result <= price:
                        steps['paid'] = result
                        break
        except BreakDialog:
            # пробрасываем исключение дальше
            raise

        # рассчитываем количество доступных посещений
        if not static_info['is_priceless']:
            prices = filter_dictlist(static_info['price_categories'], 'id', steps['category'])[0]
            if voucher_type in ('test', 'once'):
                # здесь все цены заданы жёстко, никаких отсрочек
                # оплаты не предусмотрено
                key = '%s_price' % voucher_type
                price = float(prices[key])
                steps['price'] = steps['paid'] = price
                steps['count_sold'] = 1

            once_price = float(prices['once_price'])
            steps['count_available'] = self.calculate_available_visits(
                'discount_price' in steps and steps['discount_price'] or steps['price'],
                steps['paid'], once_price, steps['count_sold']
                )
        return steps

    def assign_club(self):
        """ Метод для обработки клубных ваучеров. """

        steps = {'voucher_type': 'club'}
        card_dict = {}
        for i in self.params.static.get('card_club'):
            key = i['id']
            card_dict[key] = i
        card_list = [(k, d['title']) for k,d in card_dict.items()]

        steps['begin_date'] = None
        steps['end_date'] = None

        result = self.wizard_dialog('list', _('Card Type'), card_list)
        if not result:
            raise RuntimeWarning('Wrong Card Type')
        steps['card'] = card_dict[int(result)]
        steps['club_type'] = steps['card']['slug']
        steps['duration'] = int(result)

        card_by_id = dictlist2dict(self.params.static.get('card_club'), 'id')
        steps['price'] = card_by_id[int(result)]['price']

        cat_list = [(i['id'], i['title']) for i in card_by_id[int(result)]['price_categories']]
        result = self.wizard_dialog('list', _('Price Category'), cat_list)
        if not result:
            raise RuntimeWarning('Wrong Price Category')
        steps['category'] = int(result)

        result = self.wizard_dialog('price', _('Paid'), steps.get('price', 0.00))
        if not result:
            raise RuntimeWarning('Wrong Paid')
        steps['paid'] = float(result)

        return steps

    def assign_promo(self):
        """ Метод для обработки промо ваучеров. """

        steps = {'voucher_type': 'promo'}

        card_dict = {}
        for i in self.params.static.get('card_promo'):
            key = i['id']
            card_dict[key] = i
        card_list = [(k, d['title']) for k,d in card_dict.items()]

        try:
            result = self.wizard_dialog('list', _('Card Type'), card_list)
            if result:
                steps['card'] = card_dict[int(result)]
                steps['promo_type'] = steps['card']['slug']
                steps['price'] = steps['card'].get('price', float(0))

            # требуем оплаты полной суммы
            while True:
                price = steps.get('price', 0.00)
                result = self.wizard_dialog('price', _('Paid'), price)
                if result:
                    if float(result) == float(price):
                        steps['paid'] = float(result)
                        break
        except BreakDialog:
            # пробрасываем исключение дальше
            raise
        else:
            steps['begin_date'] = steps['card'].get('date_activation')
            steps['end_date'] = steps['card'].get('date_expiration')
            steps['count_sold'] = steps['card'].get('count_sold', 0)
            steps['count_used'] = steps['card'].get('count_used', 0)
            steps['count_available'] = steps['card'].get('count_available', 0)
        return steps

    def _price_abonement(self, steps):
        """ This method calculate the abonement price. See logic_clientcard.xml. """
        prices = filter_dictlist(self.params.static('category_team'), 'id', steps['category'])[0]

        count = int(steps['count_sold'])
        if count == 1:
            price = float(prices['once_price'])
        elif count == 4:
            price = float(prices['half_price'])
        elif count == 8:
            price = float(prices['full_price'])
        elif count > 8 and count % 8 == 0:
            price = float(prices['full_price']) * (count / 8)
        else:
            print _('Invalid usage. Why do you use count=%i' % count)
            price = float(0.0)

        steps['price'] = price

    def applyDialog(self):
        """ Apply settings. """
        if self.send_to_server():
            self.accept()
            return
        QMessageBox.warning(self, _('Warning'), _('Please fill all fields.'))

    def send_to_server(self):
        """
        Метод для сохранения информации о клиенте.

        @type  data: list of tuples
        @param data: Список двухэлементных кортежей с данными о клиенте.

        @rtype boolean
        @return: Результат выполнения операции.
        """
        data = [
            ('uuid', self.user_id),
            ('is_active', True), # статусом надо управлять на диалоге
            ('last_name', self.editLastName.text().toUtf8()),
            ('first_name', self.editFirstName.text().toUtf8()),
            ('phone', self.editPhone.text().toUtf8()),
            ('email', self.editEmail.text().toUtf8()),
            ('birth_date', self.dateBirth.date().toPyDate()),
            ('rfid', self.rfid_uuid or u''),
            ]

        # соберём информацию о скидках клиента, сохраняем
        # идентификаторы установленных скидок
        [ data.append( ('discount', i) ) for i,(o, desc) in self.discounts_by_uuid.items() if o.checkState() == Qt.Checked]

        # собираем данные о ваучерах
        data += self.tableHistory.model().get_model_as_formset()

        # передаём на сервер
        http = self.params.http
        if not http.request('/api/client/', self.user_id is None and 'POST' or 'PUT', data):
            QMessageBox.critical(self, _('Save info'), _('Unable to save: %s') % http.error_msg)
            return False
        return 'OK' == http.parse(is_json=False)

class RenterInfo(UiDlgTemplate):

    ui_file = 'uis/dlg_user_info.ui'
    params = None
    title = _('Renter\'s information')
    rent_model = None
    user_id = u'0'

    def __init__(self, parent=None):
        self.params = ParamStorage()
        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        self.tableHistory.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.rent_model = RentListModel(self)
        self.tableHistory.setModel(self.rent_model)
        #self.tableHistory.setContextMenuPolicy(Qt.CustomContextMenu)
        #self.tableHistory.customContextMenuRequested.connect(self.context_menu)

        # # добавляем на диалог все зарегистрированные виды скидок
        # for discount in self.static.get('discount_client', None): # see params
        #     item = QCheckBox('%(title)s (%(percent)s%%)' % discount)
        #     self.discounts[int(discount['id'])] = (item, discount)
        #     self.discountLayout.addWidget(item)
        # self.discountLayout.addStretch(10)

        self.buttonAssign.setText(_('Assign a rent'))
        self.connect(self.buttonAssign, SIGNAL('clicked()'), self.assign_rent)
        self.connect(self.buttonApply,  SIGNAL('clicked()'), self.apply_dialog)
        self.connect(self.buttonClose,  SIGNAL('clicked()'), self, SLOT('reject()'))

        self.buttonRFID.setDisabled(True)

    def initData(self, data={}):
        # новые записи обозначаются нулевым идентификатором
        self.user_id = data.get('id', '0')

        # Определение подсказок
        meta = [('last_name', self.editLastName),
                ('first_name', self.editFirstName),
                ('email', self.editEmail),
                ('phone', self.editPhone),
                ]
        for key, obj in meta:
            text = data.get(key, '')
            obj.setText(text)
            obj.setToolTip(text)

        for i in data.get('discount'):
            item, desc = self.discounts[i['id']]
            item.setCheckState(Qt.Checked)

        birth_date = data.get('birth_date') # it could be none while testing
        self.dateBirth.setDate(birth_date and str2date(birth_date) or \
                               QDate.currentDate())

        # заполняем список зарегистрированных аренд
        self.tableHistory.model().init_data(data.get('activity_list', []))

    def assign_rent(self):
        """ Метод отображает диалог регистрации аренды. """

        # определяем обработчик результатов диалога
        def handle(info):
            errors = []
            for k,v in info.items():
                if type(v) is str and len(v) == 0:
                    errors.append(k)
            if len(errors) > 0:
                msg = '%s\n%s' % ( _('Check the following fields:'), ', '.join(errors) )
                QMessageBox.warning(self, _('Assign Rent'), msg)
                return False
            else:
                self.tableHistory.model().insert_new(info)
                return True

        dialog = AssignRent(self, handle)
        dialog.setModal(True)
        dialog.init_data( {'rent_item_list': [], } )
        dialog.exec_()

    def apply_dialog(self):
        userinfo = {
            'last_name': self.editLastName.text().toUtf8(),
            'first_name': self.editFirstName.text().toUtf8(),
            'phone': self.editPhone.text().toUtf8(),
            'email': self.editEmail.text().toUtf8(),
            }
        if self.save_settings(userinfo):
            self.accept()

    def save_settings(self, userinfo):
        """ Метод для сохранения информации об арендаторе и его
        заказах."""

        default_response = None

        # сохраняем информацию об арендаторе
        params = { 'user_id': self.user_id, 'discounts': json.dumps( [] ) }
        params.update(userinfo)
        try:
            response = self.params.http.request_full('/manager/set_renter_info/', params)
        except HttpException, e:
            QMessageBox.critical(self, _('Save info'), _('Unable to save: %s') % e)
            return False
        else:
            user_id = response['saved_id']

        # сохраняем аренды
        title = _('Save rents')
        model = self.tableHistory.model()
        params = model.formset( initial={'user_id': user_id,} )
        print 'USERINFO:', params

        try:
            response = self.params.http.request_full('/manager/save_rent_list/', params)
        except HttpException, e:
            QMessageBox.critical(self, _('Save info'), _('Unable to save: %s') % e)
            return False
        else:
            print 'RESPONSE', response

        return True

# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from settings import userRoles
from card_list import CardListModel
from rent_list import RentListModel
from dialogs import BreakDialog, WizardListDlg, WizardSpinDlg, WizardPriceDlg, PaymentDlg
from dialogs.rfid_wait import WaitingRFID

from dialogs.assign_rent import AssignRent
from ui_dialog import UiDlgTemplate
from library import ParamStorage

from datetime import datetime, date, timedelta

from PyQt4.QtGui import *
from PyQt4.QtCore import *

ERR_VOUCHER_PAYMENT = 2101


def str2date(value):
    return datetime.strptime(value, '%Y-%m-%d').date()


class BaseUserInfo(UiDlgTemplate):

    ui_file = 'uis/dlg_user_info.ui'
    params = ParamStorage()
    model = None
    user_id = None  # новые записи обозначаются отсутствием идентификатора
    discounts_by_index = {}
    discounts_by_uuid = {}
    rfid_id = None
    rfid_uuid = None
    changed = False

    def __init__(self, parent=None):
        UiDlgTemplate.__init__(self, parent)

    def setupUi(self, *args, **kwargs):
        UiDlgTemplate.setupUi(self)

        self.tableHistory.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableHistory.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableHistory.customContextMenuRequested.connect(self.context_menu)

        # добавляем на диалог все зарегистрированные виды скидок
        discount_list = kwargs.get('discount', [])
        for index, item in enumerate(discount_list):
            checkbox = QCheckBox('%(title)s (%(percent)s%%)' % item)
            self.discounts_by_index[index] = (checkbox, item)
            self.discounts_by_uuid[item.get('uuid')] = (checkbox, item)
            self.discountLayout.addWidget(checkbox)
        self.discountLayout.addStretch(10)

        self.connect(self.buttonAssign, SIGNAL('clicked()'), self.assign_item)
        self.connect(self.buttonRFID,   SIGNAL('clicked()'), self.assign_rfid)
        self.connect(self.buttonSave,   SIGNAL('clicked()'), self.save_dialog)
        self.connect(self.buttonClose,  SIGNAL('clicked()'), self, SLOT('reject()'))

    def context_menu(self, position):
        raise RuntimeWarning('Reimplement method: context_menu().')

    def assign_rfid(self):
        """
        Метод для назначения пользователю RFID идентификатора.
        """
        def callback(rfid):
            self.rfid_code = rfid

        dialog = WaitingRFID(self, mode='client', callback=callback)
        dialog.setModal(True)
        dlgStatus = dialog.exec_()

        if QDialog.Accepted == dlgStatus:
            http = self.params.http
            if not http.request('/api/rfid/%s/' % self.rfid_code, 'POST'):
                QMessageBox.critical(self, self.tr('Client Information'), self.tr('Unable to fetch: %1').arg(http.error_msg))
                return
            status, response = http.piston()
            if status == 'DUPLICATE_ENTRY':
                QMessageBox.warning(self, self.tr('Warning'), self.tr('This RFID is used already!'))
            elif status == 'CREATED':
                self.rfid_uuid = response.get('uuid')
                self.buttonRFID.setText(self.rfid_code)
                self.buttonRFID.setDisabled(True)

    def assign_item(self):
        raise RuntimeWarning('Reimplement method: assign_item().')

    def save_user(self, *args, **kwargs):
        """
        Метод для сохранения информации о пользователе.

        @rtype: boolean
        @return: Результат выполнения операции.
        """
        mode = kwargs.get('mode', 'client')
        data = [
            ('uuid', self.user_id),
            ('is_active', True),  # статусом надо управлять на диалоге
            ('last_name', self.editLastName.text().toUtf8()),
            ('first_name', self.editFirstName.text().toUtf8()),
            ('phone', self.editPhone.text().toUtf8()),
            ('email', self.editEmail.text().toUtf8()),
            ('birth_date', self.dateBirth.date().toPyDate()),
            ('rfid', self.rfid_uuid or u''),
            ]

        # соберём информацию о скидках клиента, сохраняем
        # идентификаторы установленных скидок
        data = data + [('discount', i) for i, (o, desc) in self.discounts_by_uuid.items() if o.checkState() == Qt.Checked]

        # передаём на сервер
        dialog_title = self.tr('Saving')
        http = self.params.http
        if not http.request('/api/%s/' % mode,
                            self.user_id is None and 'POST' or 'PUT',
                            data):
            QMessageBox.critical(self, dialog_title, self.tr('Unable to save: %1').arg(http.error_msg))
            return False
        status, response = http.piston()
        if status == 'ALL_OK':
            self.user_id = response.get('uuid')
            QMessageBox.information(self, dialog_title, self.tr('Information is saved.'))
            return True
        else:
            QMessageBox.warning(self, dialog_title, self.tr('Warning!\nPlease fill all fields.'))
            return False


class RenterInfo(BaseUserInfo):

    def setupUi(self):
        self.title = self.tr('Renter Information')
        super(RenterInfo, self).setupUi(discount=self.params.static.get('discount_renter'))

        self.model = RentListModel(self)
        self.tableHistory.setModel(self.model)

        header = self.tableHistory.horizontalHeader()
        header.setStretchLastSection(False)
        header.setResizeMode(QHeaderView.ResizeToContents)
        header.setResizeMode(0, QHeaderView.Stretch)

    def context_menu(self, position):
        """
        Метод для регистрации контекстного меню.
        """
        index = self.tableHistory.indexAt(position)
        model = index.model()
        menu = QMenu()

    def initData(self, data={}):
        self.user_id = data.get('uuid')
        self.buttonAssign.setDisabled(self.user_id is None)

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

        birth_date = data.get('birth_date')  # it could be none while testing
        self.dateBirth.setDate(birth_date and str2date(birth_date) or \
                               QDate.currentDate())

        # заполняем список зарегистрированных аренд
        self.tableHistory.model().init_data(data.get('activity_list', []))

    def assign_item(self):
        """ Метод отображает диалог регистрации аренды. """

        dialog = AssignRent(self, renter=self.user_id)
        data = dict(rent_item_list=[])
        dialog.init_data(data)
        dialog.exec_()

    def save_dialog(self):
        """ Save user settings. """
        if self.save_user(mode='renter'):
            self.buttonAssign.setDisabled(False)


class ClientInfo(BaseUserInfo):

    def setupUi(self):
        self.title = self.tr('Client Information')
        super(ClientInfo, self).setupUi(discount=self.params.static.get('discount_client'))

        self.model = CardListModel(self)
        self.tableHistory.setModel(self.model)

        header = self.tableHistory.horizontalHeader()
        header.setStretchLastSection(False)
        header.setResizeMode(QHeaderView.ResizeToContents)
        header.setResizeMode(0, QHeaderView.Stretch)

    def context_menu(self, position):
        """ Create context menu."""

        index = self.tableHistory.indexAt(position)
        model = index.model()
        menu = QMenu()
        is_debt, debt_amount = model.is_debt_exist(index, True)
        cancelled = model.is_cancelled(index)
        may_prolongate = model.may_prolongate(index)

        action_payment_add = menu.addAction(self.tr('Payment'))
        action_payment_add.setDisabled(not is_debt)
        action_prolongate = menu.addAction(self.tr('Prolongate'))
        action_prolongate.setDisabled(not(cancelled and may_prolongate and not is_debt))
        action_cancel = menu.addAction(self.tr('Cancel'))
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
        self.buttonAssign.setDisabled(self.user_id is None)

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

        birth_date = data.get('birth_date', None)  # it could be none while testing
        self.dateBirth.setDate(birth_date and str2date(birth_date) or \
                               QDate.currentDate())

        rfid = data.get('rfid')
        if rfid:
            self.rfid_uuid = rfid.get('uuid')
            self.rfid_code = rfid.get('code')

            self.buttonRFID.setText(self.rfid_code)
            self.buttonRFID.setToolTip(self.tr('RFID code of this client.'))
            self.buttonRFID.setDisabled(True)

        # заполняем список приобретённых ваучеров
        self.tableHistory.model().init_data(data.get('voucher_list'))

    def save_dialog(self):
        """
        Метод для сохранения информации Save user settings. """
        if self.save_user(mode='client'):
            self.buttonAssign.setDisabled(False)

    def voucher_payment_add(self, index, initial_value=0.00):
        """ Show price dialog and register payment. """
        title = self.tr('Register payment')

        def callback(value):
            self.payment = value

        params = {
            'title': self.tr('Payment'),
            'button_back': self.tr('Cancel'),
            'button_next': self.tr('Apply'),
            'callback': callback,
            'initial_value': initial_value,
            }

        # получаем информацию о выбранном ваучере
        voucher = index.model().get_voucher_info(index)
        voucher_uuid = voucher.get('uuid')

        # запрашиваем сумму доплаты
        dialog = PaymentDlg(self, params)
        dialog.setModal(True)

        if QDialog.Accepted == dialog.exec_():
            # проводим платёж
            http = self.params.http
            if not http.request('/api/voucher/', 'PUT',
                                {'action': 'PAYMENT', 'uuid': voucher_uuid, 'amount': self.payment}):
                QMessageBox.critical(self, title, self.tr('Unable to register: %1').arg(http.error_msg))
                return
            status, response = http.piston()
            if u'ALL_OK' == status:
                paid = voucher['paid'] = self.payment + voucher.get('paid')
                available = voucher['available'] = response.get('available')
                voucher = dict(voucher,
                               paid=paid, available=available)
            else:
                # иначе сообщаем о проблеме
                QMessageBox.warning(self, title, '%s: %i\n\n%s\n\n%s' % (
                    self.tr('Error'), ERR_VOUCHER_PAYMENT,
                    self.tr('Server could not receive that payment.'),
                    self.tr('Call support team!')))

    def voucher_prolongate(self, index):
        """ Метод для пролонгации ваучера. Отображает диалог с
        календарём, позволяя продлить действие ваучера до двух недель
        от текущего дня."""
        from dlg_calendar import DlgCalendar
        title = self.tr('Voucher Prolongation')
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
                  'title': title, 'desc': self.tr('Choose the prolongation date:')}
        self.dialog = DlgCalendar(self, **params)
        self.dialog.setModal(True)
        self.dialog.setCallback(callback)
        if QDialog.Accepted == self.dialog.exec_():
            # выполняем пролонгацию на сервере
            params = {'voucher_id': voucher_id, 'prolongate_date': self.selected_date}
            if not self.http.request('/manager/voucher_prolongate/', params):
                QMessageBox.critical(self, title, self.tr('Unable to prolongate: %1').arg(self.http.error_msg))
                return
            # проверяем результат
            default_response = None
            response = self.http.parse(default_response)
            if response and 'saved_id' in response:
                QMessageBox.information(self, title, self.tr('Voucher has been prolongated sucessfully.'))
                # приводим отображаемую модель к нужному виду
                if 'end_date' in voucher:
                    voucher['end_date'] = self.selected_date
                    voucher['cancel_datetime'] = None
                    model.update(index)
            else:
                QMessageBox.critical(self, title, self.tr('Could not prolongate this voucher!'))

    def voucher_cancel(self, index):
        """
        Метод для отмены ваучера. Отображает форму "Да/Нет".
        """
        title = self.tr('Voucher Cancellation')
        # получаем информацию о ваучере
        model = index.model()
        voucher = model.get_voucher_info(index)
        voucher_uuid = voucher.get('uuid')
        if not voucher_uuid:
            raise Exception('Bad voucher id')
        # удостоверяемся в трезвом уме пользователя
        if QMessageBox.Yes == QMessageBox.question(self, title,
                                                   self.tr('Are you sure to cancel this voucher?'),
                                                   QMessageBox.Yes, QMessageBox.No):
            # отменяем ваучер
            http = self.params.http
            if not http.request('/api/voucher/', 'PUT',
                                {'action': 'CANCEL', 'uuid': voucher_uuid}):
                QMessageBox.critical(self, title, self.tr('Unable to cancel: %1').arg(http.error_msg))
                return
            response = http.parse()

            if u'OK' == unicode(response):
                QMessageBox.information(self, title, self.tr('Voucher has been cancelled sucessfully.'))
                # приводим отображаемую модель к нужному виду
                if 'cancelled' in voucher:
                    voucher['cancelled'] = datetime.now()
                    model.update(index)
            else:
                QMessageBox.critical(self, title, self.tr('Could not cancel this voucher!'))

    def wizard_dialog(self, dtype, title, data_to_fill, desc=None):
        self.wizard_data = None

        def callback(data):
            self.wizard_data = data  # id, title, voucher_type

        dialogs = {
            'list': WizardListDlg,
            'spin': WizardSpinDlg,
            'price': WizardPriceDlg,
            }

        params = {'button_back': self.tr('Cancel'), 'desc': desc}
        dialog = dialogs[dtype](self, params)
        dialog.setModal(True)
        dialog.prefill(title, data_to_fill, callback)
        if QDialog.Accepted == dialog.exec_():
            return self.wizard_data
        else:
            raise BreakDialog('Dialog is not accepted')

    def calculate_available_visits(self, voucher):
        """
        Метод для вычисления количества доступных
        посещений. Вызывается при регистрации ваучера и после
        проведения доплаты.
        """
        price = 'discount_price' in voucher and voucher.get('discount_price') or voucher.get('price')
        paid = voucher.get('paid')
        sold = voucher.get('sold')
        once = voucher.get('category').get('once')
        if float(price) - float(paid) < 0.01:
            # оплачена полная стоимость ваучера
            return int(sold)
        else:
            from math import floor
            return int(floor(paid / once))

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
            item = ('club', self.tr('Club Card'))
            card_list.append(item)
        if 0 < len(self.params.static.get('card_promo')):
            item = ('promo', self.tr('Promo Card'))
            card_list.append(item)
        return card_list

    def assign_item(self):
        """ Общий метод для добавления ваучера клиенту. Далее, в
        зависимости от выбора менеджера, происходит вызов нужного
        функционала."""

        try:
            voucher_type = self.wizard_dialog('list', self.tr('Choose the voucher\'s type'),
                                              self.possible_voucher_types())
            voucher_type_str = str(voucher_type)

            if voucher_type_str in ('flyer', 'test', 'once', 'abonement'):
                steps = self.assign_ordinary(voucher_type_str)
            elif voucher_type_str == 'club':
                steps = self.assign_club()
            elif voucher_type_str == 'promo':
                steps = self.assign_promo()
            else:
                raise Exception(self.tr('Error'))
        except BreakDialog:
            # диалог был просто закрыт, покупки нет
            return False
        else:
            # передаём информацию на сервер
            http = self.params.http
            kwargs = {
                'client': self.user_id,
                'card': steps['card'].get('uuid'),
                'is_active': u'on',
                }
            if 'category' in steps:
                kwargs['category'] = steps['category'].get('uuid')
            data = dict(steps, **kwargs)  # копируем содержимое steps и корректируем указанные поля
            if not http.request('/api/voucher/', 'POST', data):
                QMessageBox.critical(self, self.tr('Save info'), self.tr('Unable to save: %1').arg(http.error_msg))
                return False
            status, response = http.piston()
            if 'CREATED' == status:
                saved_steps = dict(steps,  # копируем содержимое steps и корректируем указанные поля
                                   uuid=response.get('uuid'),
                                   available=response.get('available'),
                                   registered=datetime.strptime(response.get('registered'), '%Y-%m-%d %H:%M:%S'))
                return self.tableHistory.model().insert_new(saved_steps)
            else:
                return False

    def assign_ordinary(self, voucher_type):
        """ Метод для добавления ваучеров обычного типа. """
        steps = {'type': voucher_type}
        steps['card'] = this_card = filter(lambda item: voucher_type == item.get('slug'),
                                           self.params.static.get('card_ordinary'))[0]

        if voucher_type in ('flyer', 'test', 'once'):
            # эти типы ваучеров могут регистрироваться на текущий день только
            steps['begin'] = steps['end'] = date.today()
        elif voucher_type in ('abonement',):
            # эти типы ваучеров определяют время жизни от первого занятия
            steps['begin'] = steps['end'] = u''

        try:
            if voucher_type in ('once', 'abonement',):
                category_list = [(i['uuid'], i['title']) for i in self.params.static.get('category_team')]
                result = self.wizard_dialog('list', self.tr('Price Category'), category_list)
                if result:
                    # из списка категорий выбираем нужную по идентификатору
                    steps['category'] = filter(lambda x: result == x.get('uuid'),
                                               self.params.static.get('category_team'))[0]
            if voucher_type in ('test',):  # WARNING: судя по таблице ваучеров, у пробного нет категории
                # назначаем самую дорогую из имеющихся категорий
                steps['category'] = reduce(lambda a, b: float(a['full']) > float(b['full']) and a or b,
                                           self.params.static.get('category_team'))

            if voucher_type == 'abonement':
                steps['used'] = 0
                steps['sold'] = sold = int(self.wizard_dialog('spin', self.tr('Visit Count'), 8))
                # вычисляем скидки и их суммарный процент
                discount_percent, discount_list = self._discount_abonement(sold)
                # вычисляем стоимость абонемента без скидок
                price = steps['price'] = self._price_abonement(steps['category'], sold)
                # вычисляем стоимость абонемента с учётом скидки
                discount_price = price - (price * discount_percent / 100)
                # если куплен полный абонемент, то стоимость
                # абонемента со скидкой не может быть ниже 2000
                # рублей.
                if sold >= 8 and discount_price < 2000.00:
                    discount_price = 2000.00
                # сохраняем результаты вычислений
                steps['discount'] = discount_list
                steps['discount_percent'] = discount_percent
                steps['discount_price'] = discount_price

                # отображаем диалог для ввода оплаченной суммы,
                # которая должна быть в диапазоне от стоимости одного
                # посещения до полной стоимости абонемента.
                once_price = steps['category'].get('once')
                while True:
                    result = float(self.wizard_dialog(
                        'price', self.tr('Paid'), discount_price,
                         self.tr('Payment range is %1 .. %2.').arg(once_price, 0, 'f', 2).arg(discount_price, 0, 'f', 2)))
                    if result >= once_price and result <= price:
                        steps['paid'] = result
                        break
        except BreakDialog:
            # какой-то из диалогов был прерван, пробрасываем исключение дальше
            raise

        # рассчитываем количество доступных посещений
        if not this_card.get('is_priceless'):
            category = steps.get('category')
            if voucher_type in ('test', 'once'):
                # здесь все цены заданы жёстко, никаких отсрочек
                # оплаты не предусмотрено
                price = float(category.get(voucher_type))
                steps['price'] = steps['paid'] = price
                steps['sold'] = 1
        return steps

    def assign_club(self):
        """ Метод для обработки клубных ваучеров. """
        steps = {'type': 'club'}
        steps['begin'] = steps['end'] = u''

        try:
            card_list = [(i['uuid'], i['title']) for i in self.params.static.get('card_club')]
            card_uuid = self.wizard_dialog('list', self.tr('Card Type'), card_list)
            if not card_uuid:
                raise RuntimeWarning('Wrong Card Type')
            steps['card'] = this_card = filter(lambda item: card_uuid == item.get('uuid'),
                                               self.params.static.get('card_club'))[0]
            steps['price'] = price = this_card.get('price')

            # отображаем диалог для ввода оплаченной суммы,
            # которая должна быть в диапазоне от стоимости одного
            # посещения до полной стоимости абонемента.
            while True:
                result = float(
                    self.wizard_dialog('price', self.tr('Paid'), price,
                        self.tr('Payment range is %(min)0.2f .. %(max)0.2f.') % \
                            dict(min=price / 2.0, max=price)))
                if result >= price / 2.0 and result <= price:
                    steps['paid'] = result
                    break
        except BreakDialog:
            # какой-то из диалогов был прерван, пробрасываем исключение дальше
            raise

        return steps

    def assign_promo(self):
        """ Метод для обработки промо ваучеров. """

        steps = {'type': 'promo'}
        steps['begin'] = steps['end'] = u''

        try:
            card_list = [(i['uuid'], i['title']) for i in self.params.static.get('card_promo')]
            card_uuid = self.wizard_dialog('list', self.tr('Card Type'), card_list)
            if not card_uuid:
                raise RuntimeWarning('Wrong Card Type')
            steps['card'] = this_card = filter(lambda item: card_uuid == item.get('uuid'),
                                               self.params.static.get('card_promo'))[0]
            steps['price'] = price = this_card.get('price')

            # требуем оплаты полной суммы
            while True:
                result = self.wizard_dialog('price', self.tr('Paid'), price)
                if result:
                    if float(result) == float(price):
                        steps['paid'] = float(result)
                        break
        except BreakDialog:
            # пробрасываем исключение дальше
            raise
        else:
            return steps

    def _price_abonement(self, category, count):
        """
        Метод вычисляет цену абонемента в зависимости от количества купленных посещений.

        @type  category: dict
        @param category: Словарь с данными категории.
        @type  count: integer
        @param count: Количество купленных посещений.

        @rtype: float
        @return: Вычисленная стоимость абонемента.
        """
        if count == 1:
            price = category.get('once')
        elif count == 4:
            price = category.get('half')
        elif count == 8:
            price = category.get('full')
        elif count > 8 and count % 8 == 0:
            price = category.get('full') * (count / 8)
        else:
            print self.tr('Invalid usage. Why do you use count=%i' % count)
            price = 0.0
        return float(price)

    def _discount_abonement(self, sold):
        uuid_list = []
        percent = 0

        if sold < 8:
            return percent, uuid_list

        # сначала проверяем клиентские скидки
        for item_uuid, (obj, desc) in self.discounts_by_uuid.items():
            if obj.checkState() == Qt.Checked:
                percent += int(desc.get('percent', 0))
                uuid_list.append(item_uuid)
        # потом проверяем скидку по количеству приобретённых посещений
        tmp_uuid = None
        tmp_percent = 0
        for discount in sorted(self.params.static.get('discount_card'),
                               lambda a, b: cmp(int(a['threshold']), int(b['threshold']))):
            if discount['threshold'] <= sold:
                tmp_uuid = discount['uuid']
                tmp_percent = int(discount['percent'])
            else:
                break  # заканчиваем цикл
        if tmp_uuid:
            percent += tmp_percent
            uuid_list.append(tmp_uuid)
        return percent, uuid_list


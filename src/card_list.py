# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from datetime import datetime, date, timedelta
import json

from library import date2str, dt2str, ParamStorage
from settings import _, DEBUG, userRoles
GET_ID_ROLE = userRoles['getObjectID']

from PyQt4.QtGui import *
from PyQt4.QtCore import *

MODEL_MAP_RAW = (
    ('card', None, _('Type'), unicode, False),
    ('category', None, _('Category'), unicode, True),
    ('price', None, _('Price'), float, False),
    ('begin', None, _('Begin'), date2str, False),
    ('end', None, _('End'), date2str, False),
    ('registered', None, _('Register'), dt2str, False),
    ('cancelled', None, _('Cancel'), dt2str, False),
    ('uuid', None, 'id', int, False), # идентификатор ваучера
    ('object', None, 'object', None, False), # всё описание ваучера
)
MODEL_MAP = list()
for name, delegate, title, action, static in MODEL_MAP_RAW[:-1]: # без последнего поля
    record = {'name': name, 'delegate': delegate,
              'title': title, 'action': action}
    MODEL_MAP.append(record)

class CardListModel(QAbstractTableModel):

    params = ParamStorage()
    free_visit_used = False

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)

        self.storage = [] # here the data is stored, as list of dictionaries
        self.hidden_fields = 1 # from end of following lists

    def init_data(self, voucher_list):
        for item in voucher_list:
            # если халявное посещение использовано, отметим это
            if item['type'] in ('voucherflyer', 'vouchertest',):
                self.free_visit_used = True

            record = []

            for name, delegate, title, action, static in MODEL_MAP_RAW:
                if name != 'object':
                    value = item.get(name, action == float and '0.00' or '--')
                else:
                    value = item
                record.append(value)

            self.storage.append(record)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), 1, self.rowCount())

    def get_voucher_info(self, index):
        return self.storage[index.row()][-1]

    def current_vouchers(self, client_id):
        """ Метод для сбора актуальной информации о ваучерах. """
        out = []
        # пробегаем по хранилищу, берём только последний элемент от
        # каждой записи (там словарь с данными), добавляем
        # идентификатор клиент, конвертируем дату/время и дампим в
        # json.
        for item in self.storage:
            voucher = item[-1]
            if 'client' not in voucher:
                voucher['client'] = {'id': client_id,}
                # перевод дат в строковую форму, перед конвертацией в json
                for key, value in voucher.items():
                    if key.endswith('_date') and isinstance(value, date):
                        voucher[key] = date2str(value)
                    elif key.endswith('_datetime') and isinstance(value, datetime):
                        voucher[key] = dt2str(value)
            out.append( json.dumps(voucher) )
        return out

    def get_model_as_formset(self, client_id):
        """ Метод для создания набора форм для сохранения данных через
        Django FormSet."""
        # основа
        voucher_list = self.current_vouchers(client_id)
        formset = {
            'form-TOTAL_FORMS': str(len(voucher_list)),
            'form-INITIAL_FORMS': '0',
            }
        # заполнение набора
        for index, record in enumerate(voucher_list):
            prefix = 'form-%i' % index
            row = {'%s-voucher' % prefix: record,}
            formset.update( row )
        return formset

    def dump(self, data=None, header=None):
        import pprint
        if data is None:
            print 'CardListModel dump is'
            pprint.pprint(self.storage)
        else:
            if header:
                print '=== %s ===' % header.upper()
            pprint.pprint(data)

    def is_cancelled(self, index):
        obj = self.get_voucher_info(index)
        return 'cancel_datetime' in obj and obj['cancel_datetime'] is not None

    def may_prolongate(self, index):
        """ Метод для определения возможности пролонгации ваучера. """
        obj = self.get_voucher_info(index)
        vtype = obj.get('voucher_type', None)
        return vtype in ('abonement',)

    def is_debt_exist(self, index, debug=False):
        """ Метод для проверки наличия долга. Метод не позволяет
        производить доплату неполностью оплаченных несохранённых
        ваучеров. Метод учитывает использованые при покупке скидки."""
        obj = self.get_voucher_info(index)
        if obj.get('id', None):
            vtype = obj.get('voucher_type', None)
            if debug:
                print 'VOUCHER:', obj
            if vtype in ('abonement', 'club', 'promo'):
                price = float( obj.get('price', 0.00) )
                paid = float( obj.get('paid', 0.00) )
                if 'discount_price' in obj: # abonement
                    price = float( obj.get('discount_price', 0.00) )
                if debug:
                    print paid < price, price - paid
                return (paid < price, price - paid)
        # в остальных случаях, считаем, что долга нет
        return (False, float(0))

    def rowCount(self, parent=None): # base class method
        if parent and parent.isValid():
            return 0
        else:
            return len(self.storage)

    def columnCount(self, parent=None):# base class method
        if parent and parent.isValid():
            return 0
        else:
            return len(MODEL_MAP) - self.hidden_fields

    def headerData(self, section, orientation, role): # base class method
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(MODEL_MAP[section].get('title', '--'))
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return QVariant(section+1) # order number
        return QVariant()

    def flags(self, index): # base class method
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsEditable

    def insert_new(self, info):
        """ Метод для вставки новой записи в модель. """
        vtype = info.get('voucher_type', None)
        template = {
            'id': 0, 'voucher_title': '',
            'category': None, 'price': 0.00,
            'reg_datetime': datetime.now(),
            'cancel_datetime': None,
            }

        # категории нет только у пробных и флаера
        if vtype in ('once', 'abonement', 'club'):
            info['category'] = filter(lambda a: a['id'] == info.get('category', None),
                                      self.params.static.get('category_team')
                                      )[0]
            template['category'] = info['category']

        # заголовок ваучера
        if vtype in ('flyer', 'test', 'once', 'abonement', 'club',):

            title = {'flyer': 'Флаер',
                     'test': 'Пробное',
                     'once': 'Разовое',
                     'abonement': 'Абонемент',
                     'club': 'Клубная',
                     }[vtype]
            template['voucher_title'] = title.decode('utf-8')
        elif vtype == 'promo':
            template['voucher_title'] = info['card'].get('title', '')

        template['price'] = info.get('price', 0.00)
        template['begin_date'] = info.get('begin_date', None)
        template['end_date'] = info.get('end_date', None)

        info.update( {'begin_date': template['begin_date'],
                      'end_date': template['end_date'],
                      'reg_datetime': template['reg_datetime'],
                      } )

        # сохраняем весь набор данных
        template['object'] = info

        # пробегаем по списку полей модели и собираем запись
        record = []
        for name, delegate, title, action, use_static in MODEL_MAP_RAW:
            value = template.get(name, None)
            record.append(value)

        self.storage.insert(0, record)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), 1, 1)

    def update(self, index):
        """ Метод для обновления полей модели после изменения
        основного объекта."""
        row = index.row()
        col = index.column()

        model_row = self.storage[index.row()]
        obj = model_row[-1]
        for col, d in enumerate(MODEL_MAP_RAW[:-1]):
            value = obj.get(d[0], None)
            model_row[col] = value

    def index_to_meta(self, index):
        row = index.row()
        col = index.column()

        field_obj = MODEL_MAP[col]
        field_name = field_obj['name']
        delegate_editor = field_obj['delegate']
        action = field_obj['action']

        return (row, col, action)

    def data(self, index, role): # переопределённый метод
        """ Метод для выдачи данных из модели. Учитывается роль и
        индекс ячейки."""

        # основные проверки
        if not index.isValid():
            return QVariant('error')
        if role == Qt.ForegroundRole:
            return self.data_ForegroundRole(index)
        #if role not in (Qt.DisplayRole, Qt.ToolTipRole, GET_ID_ROLE) :
        #    return QVariant()

        row, col, action = self.index_to_meta(index)

        if role == Qt.DisplayRole:
            record = self.storage[row]
            value = record[col]

            # для сложного типа, отображаем его название
            if type(value) is dict and 'title' in value:
                return QVariant(value.get('title'))

            if value is None or value == '--':
                return QVariant('--')
            else:
                return action(value)

        elif role == Qt.ToolTipRole:
            # вывод подсказки
            out = []
            info = self.get_voucher_info(index)
            vtype = info['type']
            if vtype in ('voucherflyer', 'vouchertest', 'voucheronce'):
                out.append( info.get('is_utilized') and _('Utilized') or _('Not utilized') )
            if vtype in ('voucherabonement', 'voucherclub', 'voucherpromo'):
                # при обработке цены, проверяем долг клиента, если он
                # есть, то показываем это
                debt, amount = self.is_debt_exist(index)
                if debt:
                    out.append( _('debt %.02f') % (amount,) )
            if vtype in ('voucherabonement',):
                # отображаем скидку, если есть
                if 'discount_price' in info:
                    price = float( info['price'] )
                    discount_price = float( info['discount_price'] )
                    discount_percent = int( info['discount_percent'] )
                    out.append( _('discount %.02f/%i%%') % (price - discount_price, discount_percent) )
            if vtype in ('voucherabonement', 'voucherpromo'):
                out.append( 'sold %i' % int( info.get('count_sold', 0) ))
                out.append( 'used %i' % int( info.get('count_used', 0) ))
                out.append( 'available %i' % int( info.get('count_available', 0) ))
            if vtype == 'voucherclub':
                out.append( 'days %i' % int( info['card'].get('count_days', 0) ))
                out.append( 'used %i' % int( info.get('count_used', 0) ))
            return QVariant('; '.join(out))
        else:
            return QVariant()

    def data_ForegroundRole(self, index):
        """ Метод для выдачи цвета шрифта в зависимости от состояния ваучера. """

        color = Qt.black
        info = self.get_voucher_info(index)

        # новые записи
        if 0 == int( info.get('id', 0) ):
            return QBrush(Qt.green)

        # проверяем активность ваучера
        if self.is_cancelled(index):
            return QBrush(Qt.gray)

        # проверяем наличие долга
        if self.is_debt_exist(index)[0]:
            return QBrush(Qt.red)

        return QBrush(color)

class CardList(QTableView):

    """ Courses list. NOT USED YET """

    def __init__(self, parent=None, params=dict()):
        QTableView.__init__(self, parent)

        self.static = params.get('static', None)

        self.verticalHeader().setResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        #self.horizontalHeader().setResizeMode(QHeaderView.Stretch)
        #self.resizeColumnsToContents()

        self.actionCardCancel = QAction(_('Cancel card'), self)
        self.actionCardCancel.setStatusTip(_('Cancel current card.'))
        self.connect(self.actionCardCancel, SIGNAL('triggered()'), self.cardCancel)

        # source model
        self.model_obj = CardListModel(self)
        self.setModel(self.model_obj)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        self.contextRow = index.row()
        menu = QMenu(self)
        menu.addAction(self.actionCardCancel)
        menu.exec_(event.globalPos())

    def cardCancel(self):
        if DEBUG:
            print 'canceled [%i]' % self.contextRow

# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from datetime import datetime, date, time, timedelta
import json

from library import date2str, dt2str, ParamStorage
from settings import DEBUG, userRoles
GET_ID_ROLE = userRoles['getObjectID']

from PyQt4.QtGui import *
from PyQt4.QtCore import *

MODEL_MAP_RAW = (
    ('card', None, QApplication.translate('card_list', 'Type'), unicode, False),
    ('category', None, QApplication.translate('card_list', 'Category'), unicode, True),
    ('price', None, QApplication.translate('card_list', 'Price'), float, False),
    ('begin', None, QApplication.translate('card_list', 'Begin'), date2str, False),
    ('end', None, QApplication.translate('card_list', 'End'), date2str, False),
    ('registered', None, QApplication.translate('card_list', 'Register'), dt2str, False),
    ('cancelled', None, QApplication.translate('card_list', 'Cancel'), dt2str, False),
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
        if not voucher_list:
            return
        for item in voucher_list:
            v_type = item.get('type')
            # если халявное посещение использовано, отметим это
            if v_type in ('flyer', 'test',):
                self.free_visit_used = True

            record = []
            object_data = {
                'type': v_type,
                }
            for name, delegate, title, action, static in MODEL_MAP_RAW:
                if name == 'object':
                    pass # добавим объект позже
                elif action is date2str:
                    value = serialized = item.get(name)
                    if value:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                elif action is dt2str:
                    value = item.get(name)
                    if value:
                        value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                else:
                    value = item.get(name, action == float and '0.00' or '--')
                object_data[name] = value
                record.append(value)
            record.append(dict(item, **object_data)) # в конце добавляем полное описание объекта
            self.storage.append(record)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), 1, self.rowCount())

    def get_voucher_info(self, index):
        return self.storage[index.row()][-1]

    def current_vouchers(self, formset_prefix):
        """ Метод для сбора актуальной информации о ваучерах. """
        out = []
        # пробегаем по хранилищу, берём только последний элемент от
        # каждой записи (там словарь с данными), добавляем
        # идентификатор клиент, конвертируем дату/время и дампим в
        # json.
        for index, item in enumerate(self.storage):
            voucher = item[-1]
            if 'client' not in voucher:
                # перевод дат в строковую форму, перед конвертацией в json
                for field, value in voucher.items():
                    if field.endswith('_date') and isinstance(value, date):
                        value = date2str(value)
                    elif field.endswith('_datetime') and isinstance(value, datetime):
                        value = dt2str(value)
                    elif type(value) is dict:
                        value = value.get('uuid')
                    elif value is None:
                        value = u''
                    key = '%s-%i-%s' % (formset_prefix, index, field)
                    out.append( (key, value) )
        return out

    def get_model_as_formset(self, formset_prefix='voucher'):
        """ Метод для создания набора форм для сохранения данных через
        Django FormSet."""
        # основа
        return [
            ('%s-INITIAL_FORMS' % formset_prefix, '0'),
            ('%s-TOTAL_FORMS' % formset_prefix, unicode(len(self.storage)) ),
            ('%s-MAX_NUM_FORMS' %formset_prefix, unicode(len(self.storage)) ),
            ] + self.current_vouchers(formset_prefix)

    def dump(self, data=None, header=None):
        import pprint
        if data:
            if header:
                print '=== %s ===' % header.upper()
            pprint.pprint(data)
        else:
            print 'CardListModel dump is'
            pprint.pprint(self.storage)

    def is_expired(self, index):
        """
        Проверка, что ваучер ещё действует.
        """
        voucher = self.get_voucher_info(index)
        end = voucher.get('end')
        if not end:
            return False # ваучер ещё не активировали (абонемент)
        return end < date.today()

    def is_cancelled(self, index):
        """
        Проверка, что ваучер не отменён.
        """
        voucher = self.get_voucher_info(index)
        return voucher.get('cancelled') is not None

    def may_prolongate(self, index):
        """ Метод для определения возможности пролонгации ваучера. """
        voucher = self.get_voucher_info(index)
        vtype = voucher.get('type')
        return vtype in ('abonement',)

    def is_debt_exist(self, index, *args, **kwargs):
        """ Метод для проверки наличия долга. Метод не позволяет
        производить доплату неполностью оплаченных несохранённых
        ваучеров. Метод учитывает использованые при покупке скидки."""
        voucher = self.get_voucher_info(index)
        if voucher.get('uuid'):
            vtype = voucher.get('type')
            if vtype in ('abonement', 'club', 'promo'):
                price = float( voucher.get('price', 0.00) )
                paid = float( voucher.get('paid', 0.00) )
                if 'discount_price' in voucher: # abonement
                    price = float( voucher.get('discount_price', 0.00) )
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

    def insert_new(self, steps):
        """ Метод для вставки новой записи в модель. """
        print 'STEPS TO INSERT', steps
        v_type = steps.get('type')
        today = date.today().strftime('%Y-%m-%d')
        record = []
        object_data = {
            'type': v_type,
            }

        value = steps['card'].get('title', '')
        object_data['card'] = steps['card']
        record.append(value)

        try:
            category = steps['category']
        except KeyError:
            value = None
        else:
            value = category.get('title', '')
        object_data['category'] = value
        record.append(value)

        value = steps.get('price', 0.0)
        object_data['price'] = value
        record.append(value)

        value = steps.get('begin', today)
        object_data['begin'] = u'' == value and None or value
        record.append(value)

        value = steps.get('end', today)
        object_data['end'] = u'' == value and None or value
        record.append(value)

        value = steps.get('registered', datetime.now())
        object_data['registered'] = value
        record.append(value)

        value = steps.get('cancelled')
        object_data['cancelled'] = value
        record.append(value)

        value = steps.get('uuid')
        object_data['uuid'] = value
        record.append(value)

        record.append(dict(steps, **object_data))

        # # категории нет только у пробных и флаера
        # if v_type in ('once', 'abonement', 'club'):
        #     steps['category'] = filter(lambda a: a['id'] == steps.get('category', None),
        #                               self.params.static.get('category_team')
        #                               )[0]
        #     template['category'] = steps['category']

        print '\nRECORD:', record
        self.storage.insert(0, record)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), 1, 1)
        return True

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

            if value is None or value in ('--', ''):
                return QVariant('--')
            else:
                return action(value)

        elif role == Qt.ToolTipRole:
            # вывод подсказки
            out = []
            info = self.get_voucher_info(index)
            vtype = info['type']
            if vtype in ('flyer', 'test', 'once',):
                out.append( info.get('is_utilized') and self.tr('Utilized') or self.tr('Not utilized') )
            if vtype in ('abonement', 'club', 'promo'):
                # при обработке цены, проверяем долг клиента, если он
                # есть, то показываем это
                debt, amount = self.is_debt_exist(index)
                if debt:
                    out.append( self.tr('debt %.02f') % (amount,) )
            if vtype == 'abonement':
                # отображаем скидку, если есть
                if 'discount_price' in info:
                    price = float( info['price'] )
                    discount_price = float( info['discount_price'] )
                    discount_percent = int( info['discount_percent'] )
                    out.append( self.tr('discount %.02f/%i%%') % (price - discount_price, discount_percent) )
                out.append( 'sold %i' % int( info.get('sold', 0) ))
                out.append( 'used %i' % int( info.get('used', 0) ))
                out.append( 'available %i' % int( info.get('available', 0) ))
            if vtype == 'club':
                out.append( 'days %i' % int( info['card'].get('days', 0) ))
                out.append( 'used %i' % int( info.get('used', 0) ))
                available = info.get('available')
                if available:
                    out.append('available %i' % int(available))
            if vtype == 'promo':
                out.append( 'used %i' % int( info.get('used', 0) ))
                out.append( 'available %i' % int( info.get('available', 0) ))
            return QVariant('; '.join(out))
        else:
            return QVariant()

    def data_ForegroundRole(self, index):
        """ Метод для выдачи цвета шрифта в зависимости от состояния ваучера. """

        info = self.get_voucher_info(index)
        if not info.get('uuid'):
            # новые записи
            return QBrush(Qt.green)
        elif self.is_expired(index) or self.is_cancelled(index):
            # завершённые и отменённые записи показываем серым
            return QBrush(Qt.gray)
        elif self.is_debt_exist(index)[0]:
            # записи с долгом показываем красным цветом
            return QBrush(Qt.red)
        else:
            # остальный записи показываем чёрным цветом
            return QBrush(Qt.black)

class CardList(QTableView):

    """ Courses list. NOT USED YET """

    def __init__(self, parent=None, params=dict()):
        QTableView.__init__(self, parent)

        self.static = params.get('static', None)

        self.verticalHeader().setResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        #self.horizontalHeader().setResizeMode(QHeaderView.Stretch)
        #self.resizeColumnsToContents()

        self.actionCardCancel = QAction(self.tr('Cancel card'), self)
        self.actionCardCancel.setStatusTip(self.tr('Cancel current card.'))
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

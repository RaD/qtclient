# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

import time, json
from datetime import datetime, date, time, timedelta
from settings import DEBUG
from library import date2str, dt2str, ParamStorage
from http import HttpException

from PyQt4.QtGui import *
from PyQt4.QtCore import *

class BaseModel(QAbstractTableModel):
    """
    Базовая модель.
    """

    # описание модели
    FIELDS = ()
    HIDDEN_FIELDS = 0
    storage = []

    # синглтон с параметрами приложения
    params = ParamStorage()

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)

    def init_data(self, event_list):
        """ Метод для заполнения модели. """
        self.storage = []

    def insert_new(self, info):
        """ Метод для вставки новой записи в модель. """
        print 'Метод insert_new() следует переопределить.'

    def export(self):
        """ Метод для экспорта информации из модели. """
        return map(lambda x: x[-1], self.storage)

    def formset(self, **kwargs):
        """ Метод для создания набора форм для сохранения данных через
        Django FormSet."""
        # основа
        if 'record_list' not in kwargs:
            record_list = self.export()
        formset = {
            'form-TOTAL_FORMS': str(len(record_list)),
            'form-INITIAL_FORMS': '0',
            }
        # заполнение набора
        for index, record in enumerate(record_list):
            prefix = 'form-%i' % index
            if 'initial' in kwargs:
                record.update( kwargs['initial'] )
            row = {'%s-record' % prefix: json.dumps(record),}
            formset.update( row )
        return formset

    ##
    ## Переопределённые методы базовой модели
    ##

    def rowCount(self, parent=None):
        if parent and parent.isValid():
            return 0
        else:
            return len(self.storage)

    def columnCount(self, parent=None):
        if parent and parent.isValid():
            return 0
        else:
            return len(self.FIELDS) - self.HIDDEN_FIELDS

    def headerData(self, section, orientation, role):
        """ Метод для вывода заголовков для полей модели. """
        # для горизонтального заголовка выводятся названия полей
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.FIELDS[section])
        # для вертикального заголовка выводятся порядковые номера записей
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return QVariant(section+1) #
        return QVariant()

    def flags(self, index):
        """ Свойства полей модели. Разрешаем только отображение."""
        return Qt.ItemIsEnabled

    def data(self, index, role):
        """ Метод для выдачи данных из модели по указанному индексу и
        для переданной роли."""

        if not index.isValid():
            return QVariant('error')

        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole:
            return QVariant(self.storage[row][col])
        elif role == Qt.ToolTipRole:
            return QVariant()
        else:
            return QVariant()

class RentEvent(BaseModel):
    """
    Модель для представления списка событий из которых состоит аренда.
    """

    # описание модели
    HIDDEN_FIELDS = 1
    storage = []

    def __init__(self, parent=None):
        BaseModel.__init__(self, parent)
        self.FIELDS = (self.tr('Week Day'), self.tr('Room'), self.tr('Category'),
                       self.tr('Begin'), self.tr('End'), None)

    def init_data(self, event_list):
        """ Метод для заполнения модели. """
        BaseModel.init_data(self, event_list)
        for i in event_list:
            record = self.prepare_record(i)
            self.storage.append(record)
        index = len(self.storage)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), 1, index)
        return True

    def insert_new(self, info):
        """ Метод для вставки новой записи в модель. Передаётся
        словарь с полями id, day_id, room_id, begin_time,
        end_time. Перед вставкой следует выполнить проверку на
        совпадение."""
        P = self.params
        key_list = ('day_id', 'room_id', 'begin_time', 'end_time')
        info_cropped = P.dict_crop(info.copy(), key_list)

        # локальная проверка на совпадение
        for obj in self.storage:
            if info_cropped == P.dict_crop(obj[-1].copy(), key_list):
                return False

        # проверка на совпадение через сервер
        title = self.tr('Check calendar')

        try:
            response = P.http.request_full('/manager/is_area_free/', info_cropped)
        except HttpException, e:
            print unicode(e)
            return False

        if not (response and response.get('free', 'no') == 'yes'):
            return False

        record = self.prepare_record(info)
        self.storage.append(record)
        index = len(self.storage)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), index, index)
        return True

    def prepare_record(self, info):
        P = self.params
        cats = {}
        map(lambda x: cats.update( { x['id']: x['title']} ), P.category_rent_list())

        record = (
            self.params.WEEK_DAYS[info['day_id']],
            P.rooms.get(info['room_id'], self.tr('Unknown')),
            cats.get(info['category_id'], self.tr('Unknown')),
            info['begin_time'],
            info['end_time'],
            info,
            )
        return record

    def price(self):
        """ Метод для определения цены аренды по всем арендованым событиям. """

        # пересчитываем сумму, для этого надо получить список
        # идентификаторов категорий, затем, используя данный
        # список получить цену для каждой категории и
        # просуммировать эти цены

        price = 0.0
        P = self.params

        cats_id = [i['category_id'] for i in self.export()]
        all_cats = P.category_rent_list()

        id_price = {}
        map(lambda x: P.dict_norm(id_price, x, 'id', 'price'), all_cats)
        for i in cats_id:
            price += id_price.get(i, 0.0)
        return price


class RentListModel(BaseModel):

    """ Модель для представления списка аренд."""

    # описание модели
    HIDDEN_FIELDS = 1
    storage = []

    def __init__(self, parent=None):
        #self.FIELDS = (self.tr('Title'), self.tr('Begin'), self.tr('End'), self.tr('Hours'), self.tr('Price'), self.tr('Paid'), None)
        self.FIELDS = ('Title', 'Begin', 'End', 'Hours', 'Price', 'Paid', None)
        BaseModel.__init__(self, parent)

    def init_data(self, event_list):
        """ Метод для заполнения модели. """
        BaseModel.init_data(self, event_list)
        for i in event_list:
            record = self.prepare_record(i)
            self.storage.append(record)
        index = len(self.storage)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), 1, index)
        return True

    def insert_new(self, info):
        """ Метод для вставки новой записи в модель. Передаётся
        словарь с полями id, day_id, room_id, begin_time,
        end_time. Перед вставкой следует выполнить проверку на
        совпадение."""

        record = self.prepare_record(info)
        self.storage.append(record)
        index = len(self.storage)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), index, index)
        return True

    def prepare_record(self, info):
        desc = QString.fromUtf8(info.get('desc')[:20])
        begin = info.get('begin_date')
        end = info.get('end_date')
        price = QString('%.02f' % info.get('price', 0.0))
        paid = QString('%.02f' % info.get('paid', 0.0))
        hours = QString('%.01f' % reduce(lambda x,y: x+y,
                                         map(lambda x: x['duration'],
                                             info.get('plan_list')),
                                         0.0))
        return (desc, begin, end, hours, price, paid, info)

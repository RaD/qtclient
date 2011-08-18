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

    Дочерние модели должны определить заголовки полей (TITLES), ключи
    полей (FIELDS).

    Для полей, которые должны отображаться особым образом (например, в
    поле находится идентификатор объекта, а надо отображать его
    текстовое описание, хранящееся на внешнем ресурсе), необходимо
    определить метод-обработчик. Шаблон имени метода: 'handler_KEY',
    где KEY - имя ключа поля из FIELDS.
    """

    # описание модели
    TITLES = ()
    FIELDS = ()
    storage = []

    # синглтон с параметрами приложения
    params = ParamStorage()

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)

    def init_data(self, event_list):
        """ Метод для заполнения модели. """
        self.storage = []

    def insert_new(self, record):
        """
        Метод для вставки новой записи в модель.
        """
        self.storage.append(record)
        index = len(self.storage)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), index, index)
        return True

    def export(self):
        """ Метод для экспорта информации из модели. """
        return self.storage

    def formset(self, **kwargs):
        """
        Метод для создания набора форм для сохранения данных через
        Django FormSet.
        """
        if 'record_list' not in kwargs:
            record_list = self.export()
        formset = [
            ('formset-TOTAL_FORMS', str(len(record_list))),
            ('formset-MAX_NUM_FORMS', str(len(record_list))),
            ('formset-INITIAL_FORMS', '0'),
            ]
        for index, record in enumerate(record_list):
            for key, value in kwargs.get('initial', {}).items(): # инжектим данные
                row = ('formset-%s-%s' % (index, key), value)
                formset.append( row )
            for key in self.FIELDS:
                row = ('formset-%s-%s' % (index, key),
                       record.get(key))
                formset.append( row )
        return formset

    def proxy(self, dictionary, key):
        """
        Метод реализующий применение обработчика для поля, если
        таковой был определён в дочерней модели.
        """
        value = dictionary.get(key, '--')
        if hasattr(self, 'handler_%s' % key):
            handler = getattr(self, 'handler_%s' % key)
            return handler(value)
        else:
            return value

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
            return len(self.FIELDS)

    def headerData(self, section, orientation, role):
        """ Метод для вывода заголовков для полей модели. """
        # для горизонтального заголовка выводятся названия полей
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.TITLES[section])
        # для вертикального заголовка выводятся порядковые номера записей
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return QVariant(section+1) #
        return QVariant()

    def flags(self, index):
        """
        Свойства полей модели. Разрешаем только отображение.
        """
        return Qt.ItemIsEnabled

    def data(self, index, role):
        """
        Метод для выдачи данных из модели по указанному индексу и для
        переданной роли.
        """
        if not index.isValid():
            return QVariant('error')

        row = index.row()
        col = index.column()
        key = self.FIELDS[col]

        if role == Qt.DisplayRole:
            value = self.proxy(self.storage[row], key)
            return QVariant(value)
        elif role == Qt.ToolTipRole:
            return QVariant()
        else:
            return QVariant()

class RentEvent(BaseModel):
    """
    Модель для представления списка событий из которых состоит аренда.
    """

    # описание модели
    FIELDS = ('weekday', 'room', 'category', 'begin_time', 'end_time',)

    def __init__(self, parent=None):
        BaseModel.__init__(self, parent)
        self.TITLES = (self.tr('Week Day'), self.tr('Room'), self.tr('Category'),
                       self.tr('Begin'), self.tr('End'),)

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

    def handler_weekday(self, value):
        """
        Обработчик для визуализации значения дня недели.
        """
        return self.params.WEEK_DAYS[int(value)]

    def handler_room(self, value):
        """
        Обработчик для визуализации наименования зала.
        """
        matched = filter(lambda x: x.get('uuid') == value,
                         self.params.static['rooms'])
        try:
            return matched[0].get('title')
        except IndexError:
            return '--'

class RentListModel(BaseModel):

    """ Модель для представления списка аренд."""

    # описание модели
    FIELDS = ('desc', 'begin_date', 'end_date', 'hours', 'price', 'paid',)

    def __init__(self, parent=None):
        BaseModel.__init__(self, parent)
        self.TITLES = (self.tr('Title'), self.tr('Begin'), self.tr('End'),
                       self.tr('Hours'), self.tr('Price'), self.tr('Paid'),)

    def init_data(self, rent_list):
        """ Метод для заполнения модели. """
        BaseModel.init_data(self, rent_list)
        for record in rent_list:
            self.storage.append(record)
        index = len(self.storage)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), 1, index)
        return True

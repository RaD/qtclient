# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

import time, json
from datetime import datetime, date, time, timedelta
from dateutil import rrule
from settings import DEBUG
from library import date2str, dt2str, ParamStorage
from http import HttpException

from PyQt4.QtGui import *
from PyQt4.QtCore import *

class DatetimeRange:
    """
    Класс для реализации определения принадлежности времени к
    определённому диапазону.
    """
    def __init__(self, low, high):
        self.low = low
        self.high = high

    def __contains__(self, dt):
        return self.low <= dt < self.high

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
    EXCLUDE = ()
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

        @type  record: dict
        @param record: Словарь с данными.

        @rtype: boolean
        @return: Результат выполнения операции.
        """
        self.storage.append(record)
        index = len(self.storage)
        self.emit(SIGNAL('rowsInserted(QModelIndex, int, int)'),
                  QModelIndex(), index, index)
        return True

    def export(self):
        """
        Метод для экспорта информации из модели.

        @rtype: list of dicts
        @return: Содержимое модели.
        """
        return self.storage

    def formset(self, **kwargs):
        """
        Метод для создания набора форм для сохранения данных через
        Django FormSet.

        @rtype: list of tuples
        @return: Список с данными набора форм.
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
                if key in self.EXCLUDE:
                    continue
                row = ('formset-%s-%s' % (index, key),
                       record.get(key))
                formset.append( row )
        return formset

    def proxy(self, dictionary, key):
        """
        Метод реализующий применение обработчика для поля, если
        таковой был определён в дочерней модели.

        @type  dictionary: dict
        @param dictionary: Словарь с данными
        @type  key: unicode
        @param key: Словарный ключ, значение для которого следует получить.
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
    FIELDS = ('weekday', 'room', 'begin_time', 'end_time', 'category', 'cost',)
    EXCLUDE = ('category', 'cost',)

    def __init__(self, parent=None):
        BaseModel.__init__(self, parent)
        self.TITLES = (self.tr('Week Day'), self.tr('Room'),
                       self.tr('Begin'), self.tr('End'),
                       self.tr('Category'), self.tr('Cost'),)

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

    def insert_new(self, record):
        """
        Метод для вставки новой записи в модель.

        @type  record: dict
        @param record: Словарь с данными.

        @rtype: boolean
        @return: Результат выполнения операции.
        """
        record = dict(record,
                      category=self.get_category_title(record),
                      cost=self.get_category_cost(record))
        return super(RentEvent, self).insert_new(record)

    def get_category(self, record):
        """
        Метод для получения категории аренды, подходящей под условия.

        @type  record: dict
        @param record: Словарь с данными события аренды.

        @rtype: dict or None
        @return: Категория аренды, подходящая под условия.
        """
        s2d = lambda x: datetime.strptime(x, '%H:%M:%S')
        value = s2d(record.get('begin_time'))

        days = ['mo', 'tu', 'we', 'th', 'fr', 'su', 'sa']
        weekday = days[int(record.get('weekday'))]

        categories = self.params.static.get('category_rent', [])
        for item in categories:
            begin = s2d(item.get('begin'))
            end = s2d(item.get('end'))
            if value in DatetimeRange(begin, end) and item.get(weekday):
                return item
        return None

    def get_category_title(self, record):
        """
        Метод для получения названия категории аренды, подходящей под условия.

        @type  record: dict
        @param record: Словарь с данными события аренды.

        @rtype: unicode
        @return: Название категории аренды.
        """
        category = self.get_category(record)
        if category:
            return category.get('title')
        else:
            return self.tr('No category')

    def get_category_cost(self, record):
        """
        Метод для вычисления стоимости события аренды, исходя из
        категории аренды, подходящей под условия.

        @type  record: dict
        @param record: Словарь с данными события аренды.

        @rtype: float
        @return: Стоимость события аренды.
        """
        s2d = lambda x: datetime.strptime(x, '%H:%M:%S')
        category = self.get_category(record)
        if category:
            begin_time = s2d(record.get('begin_time'))
            end_time = s2d(record.get('end_time'))
            duration = end_time - begin_time + timedelta(seconds=1)
            multiplier = rrule.rrule(
                rrule.DAILY,
                dtstart=datetime.strptime(record.get('begin_date'), '%Y-%m-%d'),
                until=datetime.strptime(record.get('end_date'), '%Y-%m-%d'),
                byweekday=int(record.get('weekday'))).count()
            return duration.seconds / 3600.0 * float(category.get('price')) * multiplier
        else:
            return self.tr('Unknown')

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
    """
    Модель для представления списка аренд.
    """
    FIELDS = ('desc', 'begin_date', 'end_date', 'hours', 'price', 'paid',)
    EXCLUDE = ('desc', 'begin_date', 'end_date', 'hours', 'price', 'paid',)

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

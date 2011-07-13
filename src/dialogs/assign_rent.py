# -*- coding: utf-8 -*-
# (c) 2010-2011 Ruslan Popov <ruslan.popov@gmail.com>

from settings import _, userRoles, WEEK_DAYS
from library import ParamStorage
from ui_dialog import UiDlgTemplate
from dlg_calendar import DlgCalendar
from http import Http
from rent_list import RentPlace

from PyQt4.QtGui import *
from PyQt4.QtCore import *

from datetime import datetime, date, time, timedelta

GET_ID_ROLE = userRoles['getObjectID']

##
##
##

class AddItem(UiDlgTemplate):

    """ Класс реализует диалог для добавления части аренды. """

    ui_file = 'uis/dlg_add_rent.ui'
    callback = None
    params = None
    event_id = 0

    def __init__(self, parent, callback):
        self.callback = callback
        self.params = ParamStorage()

        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        """ Метод настройки вида диалога. """
        UiDlgTemplate.setupUi(self)

        # границы действия элементов диалога
        rangeBegin = (QTime(8, 0), QTime(23, 30))
        rangeEnd = (QTime(8, 29), QTime(23, 59))
        # назначение границ действия для элементов диалога
        self.set_timeedit(self.editBegin, self.sliderBegin, rangeBegin)
        self.set_timeedit(self.editEnd, self.sliderEnd, rangeEnd)
        self.set_slider(self.sliderBegin, self.editBegin, rangeBegin, 'begin')
        self.set_slider(self.sliderEnd, self.editEnd, rangeEnd, 'end')

        # время начала должно быть меньше времени завершения
        def tune_end_widget(t):
            new_time = datetime.combine(datetime.today(), t.toPyTime()) + timedelta(minutes=29)
            self.editEnd.setMinimumTime(QTime(new_time.time()))
        self.editBegin.timeChanged.connect(tune_end_widget)

        # заполнение выпадашек
        self.fill_combo_days()
        self.fill_combo_rooms()
        self.fill_combo_categories()

        # подключение обработчиков событий
        self.connect(self.buttonOK, SIGNAL('clicked()'), self.apply_dialog)
        self.connect(self.buttonCancel,  SIGNAL('clicked()'), self, SLOT('reject()'))

    def set_timeedit(self, widget, slider, value):
        """ Метод настройки QTimeEdit. """
        widget.setTime(value[0])
        widget.setTimeRange(*value)

        def change_slider(x):
            """ Метод для изменения значения QTimeEdit по значению,
            переданному от QSlider."""
            slider.setValue(x.hour() * 60 + x.minute())

        widget.timeChanged.connect(change_slider)

    def set_slider(self, widget, timeedit, value, wtype):
        """ Метод настройки QSlider. """
        time_tuple = (value[0].hour() * 60 + value[0].minute(), value[1].hour() * 60 + value[1].minute())
        widget.setSingleStep(30) # полчаса
        widget.setTickInterval(30) # полчаса
        widget.setRange(*time_tuple)

        range_tuple = {'begin': (0, 30), 'end': (29, 59)}[wtype]

        def change_timeedit(x):
            """ Метод для изменения значения QSlider по значению,
            переданному от QTimeEdit."""
            hour = x/60
            minute = x%60
            if int(minute) in xrange(*range_tuple):
                minute = range_tuple[0]
            else:
                if 'wtype' == 'begin':
                    minute = range_tuple[1]
                else:
                    if minute < range_tuple[0]:
                        hour -= 1
                    minute = range_tuple[1]
            timeedit.setTime(QTime(hour, minute))

        widget.valueChanged.connect(change_timeedit)

    def fill_combo_days(self):
        """ Метод для заполнения списка с днями недели. """
        for i, title in enumerate(WEEK_DAYS):
            self.cbDay.addItem(title, QVariant(i))

    def fill_combo_rooms(self):
        """ Метод для заполнения списка с залами. """
        for i, title in self.params.rooms.items():
            self.cbRoom.addItem(title, QVariant(i))

    def fill_combo_categories(self):
        """ Метод для заполнения списка с категориями. """
        # сохраняем информацию об арендаторе
        P = self.params
        cats_full = P.category_rent_list()
        cats_tuple = map(P.mapper(P.dict_tuple, ['id', 'title']), cats_full)
        for i, title in cats_tuple:
            self.cbCategory.addItem(title, QVariant(i))

    def _combo_current(self, widget):
        """ Вспомогательный метод для получения данных для выбранного
        элемента выпадающего списка."""
        index = widget.currentIndex()
        item_id, ok = widget.itemData(index).toInt()
        return item_id

    def apply_dialog(self):
        """ Метод для получения данных из диалога. """
        assert self.callback is not None
        begin = self.editBegin.dateTime().toPyDateTime()
        end = self.editEnd.dateTime().toPyDateTime()
        duration = float((end - begin).seconds + 60) / 3600
        params = {'id': self.event_id,
                  'day_id': self._combo_current(self.cbDay),
                  'room_id': self._combo_current(self.cbRoom),
                  'category_id': self._combo_current(self.cbCategory),
                  'begin_time': begin.time().strftime('%H:%M:00'),
                  'end_time': end.time().strftime('%H:%M:59'),
                  'duration': duration,}
        if self.callback(params):
            self.accept()

##
##
##

class AssignRent(UiDlgTemplate):

    """ Класс реализует диалог для добавления аренды. """

    ui_file = 'uis/dlg_assign_rent.ui'
    callback = None
    model = None
    price = 0.0

    def __init__(self, parent, callback):
        self.callback = callback
        self.params = ParamStorage()

        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        self.spinPaid.setMaximum(1000000)

        # настраиваем отображение событий аренды
        self.model = RentPlace(self)
        self.tableItems.setModel(self.model)
        self.tableItems.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.connect(self.toolBegin, SIGNAL('clicked()'), lambda: self.show_calendar(self.dateBegin))
        self.connect(self.toolEnd, SIGNAL('clicked()'), lambda: self.show_calendar(self.dateEnd))
        self.connect(self.buttonToday, SIGNAL('clicked()'), self.set_date_today)

        self.connect(self.buttonAdd, SIGNAL('clicked()'), self.add_item)
        self.connect(self.buttonApply, SIGNAL('clicked()'), self.apply_dialog)
        self.connect(self.buttonCancel,  SIGNAL('clicked()'), self, SLOT('reject()'))

    def init_data(self, data=dict()):
        # новые записи обозначаются нулевым идентификатором
        self.rent_id = data.get('id', '0')

        # заполняем список зарегистрированных событий аренд
        self.tableItems.model().init_data(
            data.get('rent_item_list', [])
            )



    def set_date_today(self):
        """ Метод для установки сегодняшней даты. """
        today = QDate(date.today())
        self.dateBegin.setDate(today)
        self.dateEnd.setDate(today)

    def show_calendar(self, widget):
        """ Метод для отображения диалога с календарём. """

        # определяем обработчик результатов диалога
        def handle(selected_date):
            widget.setDate(selected_date)

        params = {'title': _('Choose a date')}
        self.dialog = DlgCalendar(self, **params)
        self.dialog.setModal(True)
        self.dialog.setCallback(handle)
        self.dialog.exec_()

    def add_item(self):
        """ Метод для отображения диалога для ввода информации о событии аренды. """

        # определяем обработчик результатов диалога
        def handle(info):
            model = self.tableItems.model()
            done = model.insert_new(info)
            if not done:
                QMessageBox.warning(self, _('Assign rent event'), _('Unable to assign: place already busy.'))
                return False

            self.price = model.price()
            self.spinPaid.setValue(self.price)

            return True

        self.dialog = AddItem(self, handle)
        self.dialog.setModal(True)
        self.dialog.exec_()

    def apply_dialog(self):
        """ Метод для получения данных из диалога. Диалог вызывается
        из user_info.RenterInfo.assign_rent."""
        assert self.callback is not None
        params = {'title': unicode(self.editTitle.text()).encode('utf-8'),
                  'desc': unicode(self.editDesc.toPlainText()).encode('utf-8'),
                  'begin_date': self.dateBegin.date().toPyDate().strftime('%Y-%m-%d'),
                  'end_date': self.dateEnd.date().toPyDate().strftime('%Y-%m-%d'),
                  'price': self.price,
                  'paid': self.spinPaid.value(),
                  'events': self.tableItems.model().export(),}
        if self.callback(params):
            self.accept()

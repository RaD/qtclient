# -*- coding: utf-8 -*-
# (c) 2010-2011 Ruslan Popov <ruslan.popov@gmail.com>

from settings import userRoles
from library import ParamStorage
from ui_dialog import UiDlgTemplate
from dlg_calendar import DlgCalendar
from rent_list import RentEvent

from PyQt4.QtGui import *
from PyQt4.QtCore import *

from datetime import datetime, date, time, timedelta

GET_ID_ROLE = userRoles['getObjectID']

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
        for i, title in enumerate(self.params.WEEK_DAYS):
            self.cbDay.addItem(title, QVariant(i))

    def fill_combo_rooms(self):
        """ Метод для заполнения списка с залами. """
        for item in self.params.static.get('rooms'):
            self.cbRoom.addItem(item.get('title'),
                                QVariant(item.get('uuid')))

    def fill_combo_categories(self):
        """ Метод для заполнения списка с категориями. """
        # сохраняем информацию об арендаторе
        for item in self.params.static.get('category_rent'):
            self.cbCategory.addItem(item.get('title'),
                                    QVariant(item.get('uuid')))

    def _combo_current(self, widget):
        """ Вспомогательный метод для получения данных для выбранного
        элемента выпадающего списка."""
        index = widget.currentIndex()
        return widget.itemData(index) # uuid

    def apply_dialog(self):
        """ Метод для получения данных из диалога. """
        assert self.callback is not None
        q2u = lambda x: unicode(self._combo_current(x).toPyObject())
        begin = self.editBegin.dateTime().toPyDateTime()
        end = self.editEnd.dateTime().toPyDateTime()
        duration = float((end - begin).seconds + 60) / 3600
        params = {'id': self.event_id,
                  'weekday': q2u(self.cbDay),
                  'room': q2u(self.cbRoom),
                  'category_uuid': q2u(self.cbCategory),
                  'begin_time': begin.time().strftime('%H:%M:00'),
                  'end_time': end.time().strftime('%H:%M:59'),
                  'duration': duration,}
        if self.callback(params):
            self.accept()

##
##
##

class AssignRent(UiDlgTemplate):
    """
    Класс диалога для добавления аренды.
    """
    ui_file = 'uis/dlg_assign_rent.ui'
    params = ParamStorage()
    user_id = None
    model = None

    def __init__(self, parent, *args, **kwargs):
        self.user_id = kwargs.get('renter')
        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        # настраиваем отображение событий аренды
        self.model = RentEvent(self)
        self.tableItems.setModel(self.model)
        self.tableItems.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.connect(self.toolBegin, SIGNAL('clicked()'), lambda: self.show_calendar(self.dateBegin))
        self.connect(self.toolEnd, SIGNAL('clicked()'), lambda: self.show_calendar(self.dateEnd))
        self.connect(self.buttonToday, SIGNAL('clicked()'), self.set_date_today)

        self.connect(self.buttonAdd, SIGNAL('clicked()'), self.add_item)
        self.connect(self.buttonSave, SIGNAL('clicked()'), self.save_rent)
        self.connect(self.buttonClose,  SIGNAL('clicked()'), self, SLOT('reject()'))

    def init_data(self, data=dict()):
        self.rent_id = data.get('uuid')
        # для новой аренды сразу заполняем даты начала и конца
        if not self.rent_id:
            self.set_date_today()
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

        params = {'title': self.tr('Choose a date')}
        self.dialog = DlgCalendar(self, **params)
        self.dialog.setModal(True)
        self.dialog.setCallback(handle)
        self.dialog.exec_()

    def add_item(self):
        """ Метод для отображения диалога для ввода информации о событии аренды. """
        self.dialog = AddItem(self, callback=self.add_item_handle)
        self.dialog.setModal(True)
        self.dialog.exec_()

    def add_item_handle(self, data):
        """
        Метод для обработки данных от диалога назначения события аренды.

        @type  data: dict
        @param data: Словарь с данными диалога.

        @rtype: boolean
        @return: Возможность размещения события на расписании.
        """
        d2s = lambda x: x.date().toPyDate().strftime('%Y-%m-%d')
        mbox_title = self.tr('Assign rent event')
        # дополняем переданные данные диапазоном дат, в котором
        # действуют события
        params = dict(data,
                      begin_date = d2s(self.dateBegin),
                      end_date = d2s(self.dateEnd))
        # делаем проверку через сервер
        http = self.params.http
        if not http.request('/api/event/', 'POST', params):
            QMessageBox.critical(self, mbox_title,
                                 self.tr('Unable to save: %1').arg(http.error_msg))
            return
        status, response = http.piston()
        if status == 'ALL_OK':
            # добавляем информацию о событии в модель
            if  self.model.insert_new(params):
                #self.price = self.model.price()
                return True

            QMessageBox.warning(self, mbox_title,
                                self.tr('Unable to assign: place already busy.'))
        elif status == 'DUPLICATE_ENTRY':
            QMessageBox.warning(self, mbox_title,
                                self.tr('Unable to assign: place already busy.'))
        else:
            QMessageBox.warning(self, mbox_title,
                                self.tr('Unknown answer: %1').arg(status))
        return False

    def save_rent(self):
        """ Метод для получения данных из диалога. Диалог вызывается
        из user_info.RenterInfo.assign_item."""
        self.begin_date = self.dateBegin.date().toPyDate().strftime('%Y-%m-%d')
        self.end_date = self.dateEnd.date().toPyDate().strftime('%Y-%m-%d')
        params = {
            'renter': self.user_id,
            'desc': unicode(self.editDesc.toPlainText()).encode('utf-8'),
            }
        http = self.params.http
        if not http.request('/api/rent/', 'POST', params):
            QMessageBox.critical(self, self.tr('Rent Save'), self.tr('Unable to save: %1').arg(http.error_msg))
            return

        dialog_title = self.tr('Rent Save')
        status, response = http.piston()
        if status == 'CREATED':
            self.rent_id = response.get('uuid')
            self.buttonAdd.setDisabled(False)
            QMessageBox.information(self, dialog_title, self.tr('Information is saved.'))
        else:
            QMessageBox.critical(self, dialog_title, self.tr('Unable to save: %1').arg(status))

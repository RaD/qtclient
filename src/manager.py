#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

import sys, re, time
from datetime import datetime, timedelta
from os.path import dirname, join

from http import WebResource
from event_storage import Event
from qtschedule import QtSchedule
from printer import Printer
#from team_tree import TreeModel

from dialogs.rfid_wait import WaitingRFID
from dialogs.searching import Searching
from dialogs.user_info import ClientInfo, RenterInfo
from dlg_settings import DlgSettings
from dlg_login import DlgLogin
from dlg_event_assign import DlgEventAssign
from dlg_event_info import EventInfo
from dlg_calendar import DlgCalendar
from dlg_accounting import DlgAccounting

from settings import DEBUG, VERSION
DEBUG_COMMON, DEBUG_RFID, DEBUG_PRINTER = DEBUG

from library import ParamStorage

from PyQt4.QtGui import *
from PyQt4.QtCore import *

MENU_DISABLED = 1
MENU_LOGGED_IN = 2
MENU_LOGGED_OUT = 4
MENU_LOGGED_ANY = MENU_LOGGED_IN | MENU_LOGGED_OUT
MENU_RFID = 8
MENU_PRINTER = 16

class MainWindow(QMainWindow):

    params = ParamStorage() # синглтон для хранения данных
    menu_actions = []
    menu_desc = None

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)

        self.setWindowIcon(QIcon('/usr/share/pixmaps/advisor-client.xpm'))

        self.mimes = {'team': 'application/x-team-item',
                      'event':  'application/x-calendar-event',
                      }
        self.tree = []
        self.rfid_id = None

        self.params.init_settings(obj=QSettings(), main_window=self)
        self.params.WEEK_DAYS = (
            self.tr('Monday'),
            self.tr('Tuesday'),
            self.tr('Wednesday'),
            self.tr('Thursday'),
            self.tr('Friday'),
            self.tr('Saturday'),
            self.tr('Sunday'),
            )

        self.params.logged_in = False
        self.params.work_hours = (8, 24)
        self.params.quant = timedelta(minutes=30)
        self.params.multiplier = timedelta(hours=1).seconds / self.params.quant.seconds

        self.menus = []
        self.menu_desc = self.app_menu()
        self.create_menus(self.menu_desc)
        self.menu_state(MENU_LOGGED_OUT)
        self.setup_views()

        # если сервер не определён, показываем диалог настройки приложения
        settings = QSettings()
        settings.beginGroup('network')
        host = settings.value('addressHttpServer', QVariant('WrongHost'))
        settings.endGroup()

        if 'WrongHost' == host.toString():
            self.app_settings()

        self.webresource = WebResource()
        self.params.http = self.webresource.get(self)

        self.baseTitle = self.tr('Manager\'s interface')
        self.logoutTitle()
        self.statusBar().showMessage(self.tr('Ready'), 2000)
        self.resize(640, 480)

    def loggedTitle(self, response):
        last_name = response.get('last_name')
        first_name = response.get('first_name')
        if len(last_name) > 0 or len(first_name) > 0:
            self.setWindowTitle('%s : %s %s' % (self.baseTitle, last_name, first_name))
        else:
            self.setWindowTitle('%s : %s' % (self.baseTitle, response.get('username')))

    def logoutTitle(self):
        self.setWindowTitle('%s : %s' % (self.baseTitle, self.tr('Login to start session')))

    def get_dynamic(self):
        self.bpMonday.setText(self.schedule.model().getMonday().strftime('%d/%m/%Y'))
        self.bpSunday.setText(self.schedule.model().getSunday().strftime('%d/%m/%Y'))

    def get_static(self):
        """
        Метод для получения статической информации с сервера.
        """
        if not self.params.http.request('/api/static/', 'GET', {}):
            QMessageBox.critical(self, self.tr('Static info'), self.tr('Unable to fetch: %s') % self.params.http.error_msg)
            return
        data = self.params.http.parse()
        if type(data) is dict and data.get('status') == 401:
            return None
        else:
            return data

    def update_interface(self):
        """ This method updates application's interface using static
        information obtained in previous method. """
        # rooms
        rooms = self.params.static.get('rooms')
        if rooms:
            for item in rooms:
                uu_id = item.get('uuid')
                title = item.get('title')
                buttonFilter = QPushButton(title)
                buttonFilter.setCheckable(True)
                buttonFilter.setDisabled(True)
                self.panelRooms.addWidget(buttonFilter)
                self.connect(buttonFilter, SIGNAL('clicked()'),
                             self.prepare_filter(uu_id, title))

    def printer_init(self):
        self.params.printer = Printer(template=self.params.static.get('printer'))
        run_it = True
        def show_printer_status():
            ok, tip = self.params.printer.get_status()
            self.printer_widget.setToolTip(tip)
            if ok:
                msg = self.tr('Printer is ready')
            else:
                msg = self.tr('Printer is not ready')
            self.printer_widget.setText(msg)
        self.printer_refresh = self.makeTimer(show_printer_status,
                                              self.params.printer.refresh_timeout,
                                              run_it)

    def prepare_filter(self, id, title):
        def handler():
            self.statusBar().showMessage(self.tr('Filter: Room "%s" is changed its state') % title)
        return handler

    def setup_views(self):
        self.panelRooms = QHBoxLayout()

        self.schedule = QtSchedule(self)

        self.bpMonday = QLabel('--/--/----')
        self.bpSunday = QLabel('--/--/----')
        self.buttonPrev = QPushButton(self.tr('<<'))
        self.buttonNext = QPushButton(self.tr('>>'))
        self.buttonToday = QPushButton(self.tr('Today'))
        self.buttonPrev.setDisabled(True)
        self.buttonNext.setDisabled(True)
        self.buttonToday.setDisabled(True)

        # callback helper function
        def prev_week():
            week_range = self.schedule.model().showPrevWeek()
            self.showWeekRange(week_range)
        def next_week():
            week_range = self.schedule.model().showNextWeek()
            self.showWeekRange(week_range)
        def today():
            week_range = self.schedule.model().showCurrWeek()
            self.showWeekRange(week_range)

        self.connect(self.buttonPrev, SIGNAL('clicked()'), prev_week)
        self.connect(self.buttonNext, SIGNAL('clicked()'), next_week)
        self.connect(self.buttonToday, SIGNAL('clicked()'), today)

        bottomPanel = QHBoxLayout()
        bottomPanel.addWidget(QLabel(self.tr('Week:')))
        bottomPanel.addWidget(self.bpMonday)
        bottomPanel.addWidget(QLabel('-'))
        bottomPanel.addWidget(self.bpSunday)
        bottomPanel.addStretch(1)
        bottomPanel.addWidget(self.buttonPrev)
        bottomPanel.addWidget(self.buttonToday)
        bottomPanel.addWidget(self.buttonNext)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(self.panelRooms)
        mainLayout.addWidget(self.schedule)
        mainLayout.addLayout(bottomPanel)

        mainWidget = QWidget()
        mainWidget.setLayout(mainLayout)

        self.setCentralWidget(mainWidget)

        self.printer_widget = QLabel('--', self.statusBar())
        self.printer_widget.setToolTip(u'Initialization in progress')
        self.statusBar().addPermanentWidget(self.printer_widget)

    def showWeekRange(self, week_range):
        if self.schedule.model().getShowMode() == 'week':
            monday, sunday = week_range
            self.bpMonday.setText(monday.strftime('%d/%m/%Y'))
            self.bpSunday.setText(sunday.strftime('%d/%m/%Y'))

    def getMime(self, name):
        return self.mimes.get(name, None)

    def app_menu(self):
        return [
            (self.tr('File'), [
                (self.tr('Open'), 'Ctrl+I', 'open_session', self.tr('Open user session.'), MENU_LOGGED_OUT),
                (self.tr('Close'), '', 'close_session', self.tr('Close user session.'), MENU_LOGGED_IN),
                None,
                (self.tr('Settings'), 'Ctrl+S', 'app_settings', self.tr('Manage the application settings.'), MENU_LOGGED_ANY),
                None,
                (self.tr('Exit'), '', 'close', self.tr('Close the application.'), MENU_LOGGED_ANY),
                ]
             ),
            (self.tr('Client'), [
                (self.tr('New'), 'Ctrl+N', 'client_new', self.tr('Register new client.'), MENU_LOGGED_IN),
                (self.tr('Search by RFID'), 'Ctrl+D', 'client_search_rfid', self.tr('Search a client with its RFID card.'), MENU_LOGGED_IN | MENU_RFID),
                (self.tr('Search by name'), 'Ctrl+F', 'client_search_name', self.tr('Search a client with its name.'), MENU_LOGGED_IN),
                ]
             ),
            (self.tr('Renter'), [
                (self.tr('New'), 'Ctrl+M', 'renter_new', self.tr('Register new renter.'), MENU_LOGGED_IN),
                (self.tr('Search by name'), 'Ctrl+G', 'renter_search_name', self.tr('Search a renter with its name.'), MENU_LOGGED_IN),
                ]
              ),
            (self.tr('Help'), [
                (self.tr('About'), '', 'help_about', self.tr('About application dialog.'), MENU_LOGGED_ANY),
                ]
             ),
            ]

    def create_menus(self, desc):
        """
        Метод генерирует по переданному описанию меню приложения.

        Использование: Опишите меню со всеми его действиями,
        реализуйте обработчики для каждого элемента меню, передайте
        описание в данный метод.
        """
        for topic, info in desc:
            action_handlers = []
            menu = self.menuBar().addMenu(topic)
            for item in info:
                if item is None:
                    menu.addSeparator()
                    continue
                else:
                    title, short, name, desc, state = item
                    setattr(self, 'act_%s' % name, QAction(title, self))
                    action = getattr(self, 'act_%s' % name)
                    action.setShortcut(short)
                    action.setStatusTip(desc)
                    self.connect(action, SIGNAL('triggered()'), getattr(self, name))
                    menu.addAction(action)
                    self.menus.append(menu)
                    action_handlers.append( (action, state,) )
            self.menu_actions.append( action_handlers )

    def menu_state(self, state):
        """
        Метод для смены состояния меню.
        """
        BITS = {
            'DISABLED': 0,
            'LOGGED_IN': 1,
            'LOGGED_OUT': 2,
            'RFID': 3,
            'PRINTER': 4,
            }

        def is_bit_set(value, bitname):
            try:
                bitnum = BITS[bitname]
            except KeyError:
                return False
            else:
                return (state & (1 << bitnum)) != 0

        for actions in self.menu_actions:
            for action, state in actions:
                if is_bit_set(state, 'DISABLED'):
                    action.setDisabled(True)
                    continue

                if not self.params.logged_in:
                    if is_bit_set(state, 'LOGGED_OUT'):
                        action.setDisabled(False)
                    else:
                        action.setDisabled(True)
                    continue

                if self.params.logged_in:
                    if is_bit_set(state, 'LOGGED_IN'):
                        disable = False
                        if is_bit_set(state, 'RFID'): # and RFID not present
                            disable = True
                        elif is_bit_set(state, 'PRINTER'): # and PRINTER not present
                            disable = True
                        action.setDisabled(disable)
                    else:
                        action.setDisabled(True)
                    continue


    def interface_disable(self, state):
        # Enable menu's action
        self.menu_state(state)
        # Enable the navigation buttons
        self.buttonPrev.setDisabled(not self.params.logged_in)
        self.buttonNext.setDisabled(not self.params.logged_in)
        self.buttonToday.setDisabled(not self.params.logged_in)

    def refresh_data(self):
        """ This method get the data from a server. It call periodically using timer. """

        # Do nothing until user authoruized
        if not self.params.http.is_session_open():
            return
        # Just refresh the calendar's model
        self.schedule.model().update

    # Menu handlers: The begin

    def open_session(self):
        def callback(credentials):
            self.credentials = dict(credentials,
                                    version='.'.join(map(str, self.params.version)))

        connecting_to = u'%s %s' % (
            self.params.http.hostport,
            self.webresource.use_ssl and self.tr('Secure') or self.tr('Unsecure'),
            )
        self.dialog = DlgLogin(self, connecting_to=connecting_to)
        self.dialog.setCallback(callback)
        self.dialog.setModal(True)
        dlgStatus = self.dialog.exec_()

        dialog_title = self.tr('Open session')
        http = self.params.http
        if QDialog.Accepted == dlgStatus:
            if not http.request('/api/login/', 'POST', credentials=self.credentials):
                QMessageBox.critical(self, dialog_title,
                                     self.tr('Unable to make request: %1').arg(http.error_msg))
                return

            default_response = None
            status, response = http.piston()
            if status == 'ALL_OK':
                self.params.logged_in = True
                self.loggedTitle(response)

                # подгружаем статическую информацию и список залов
                static = self.get_static()
                if not static:
                    print 'Check static!'
                    return
                self.params.static = static

                rooms_by_index = {}
                rooms_by_uuid = {}
                for index, room in enumerate(self.params.static.get('rooms')):
                    room_uuid = room.get('uuid')
                    rooms_by_index[index] = room
                    rooms_by_uuid[room_uuid] = index
                self.params.static['rooms_by_index'] = rooms_by_index
                self.params.static['rooms_by_uuid'] = rooms_by_uuid

                # здесь только правим текстовые метки
                self.get_dynamic()
                # изменяем свойства элементов интерфейса
                self.update_interface()
                # загружаем информацию о занятиях на расписание
                self.schedule.model().showCurrWeek()

                # # run refresh timer
                from settings import SCHEDULE_REFRESH_TIMEOUT
                self.refreshTimer = self.makeTimer(self.refresh_data, SCHEDULE_REFRESH_TIMEOUT, True)

                self.printer_init()
                self.interface_disable(MENU_LOGGED_IN | MENU_RFID | MENU_PRINTER)
            elif status == 'NOT_IMPLEMENTED':
                QMessageBox.information(self, dialog_title,
                                        self.tr('Protocol is deprecated!'))
            elif status == 'BAD_REQUEST':
                QMessageBox.information(self, dialog_title,
                                        self.tr('No protocol version found!'))
            else:
                QMessageBox.warning(self, dialog_title,
                                    self.tr('It seems you\'ve entered wrong login/password.'))

    def close_session(self):
        self.params.logged_in = False
        self.interface_disable(MENU_LOGGED_OUT)
        self.setWindowTitle('%s : %s' % (self.baseTitle, self.tr('Open user session')))
        self.schedule.model().storage_init()

        # clear rooms layout
        layout = self.panelRooms
        while layout.count() > 0:
            item = layout.takeAt(0)
            if not item:
                continue
            w = item.widget()
            if w:
                w.deleteLater()

    def app_settings(self):
        self.dialog = DlgSettings(self)
        self.dialog.setModal(True)
        self.dialog.exec_()
        self.get_dynamic()
        self.params.http.disconnect()
        self.params.http = self.webresource.get(self)
        self.params.http.connect()

    def client_new(self, klass=ClientInfo):
        self.user_new(klass)

    def renter_new(self, klass=RenterInfo):
        self.user_new(klass)

    def client_search_name(self, klass=ClientInfo, mode='client'):
        self.user_search_name(klass, mode)

    def renter_search_name(self, klass=RenterInfo, mode='renter'):
        self.user_search_name(klass, mode)

    def client_search_rfid(self, klass=ClientInfo, mode='client'):
        self.user_search_rfid(klass, mode)

    def renter_search_rfid(self, klass=RenterInfo, mode='renter'):
        return
        self.user_search_rfid(klass, mode)

    def user_new(self, klass):
        self.dialog = klass(self)
        self.dialog.setModal(True)
        self.dialog.exec_()

    def user_search_rfid(self, klass, mode):
        """
        Метод для поиска клиента по RFID.
        """
        def callback(rfid):
            self.rfid_id = rfid

        if self.params.logged_in:
            dialog = WaitingRFID(self, mode=mode, callback=callback)
            dialog.setModal(True)
            if QDialog.Accepted == dialog.exec_() and self.rfid_id:
                h = self.params.http
                if not h.request('/api/%s/%s/' % (mode, self.rfid_id), 'GET', force=True):
                    QMessageBox.critical(self, self.tr('Client info'), self.tr('Unable to fetch: %s') % h.error_msg)
                    return
                response = h.parse()

                if 0 == len(response):
                    QMessageBox.warning(self, self.tr('Warning'),
                                        self.tr('This RFID belongs to nobody.'))
                else:
                    self.dialog = klass(self)
                    self.dialog.setModal(True)
                    self.dialog.initData(response[0])
                    self.dialog.exec_()
                    del(self.dialog)
                    self.rfid_id = None

    def user_search_name(self, klass, mode):
        def callback(user):
            self.user = user

        if self.params.logged_in:
            self.dialog = Searching(self, mode=mode)
            self.dialog.setModal(True)
            self.dialog.setCallback(callback)
            if QDialog.Accepted == self.dialog.exec_():
                self.dialog = klass(self)
                self.dialog.setModal(True)
                self.dialog.initData(self.user)
                self.dialog.exec_()
                del(self.dialog)

    def help_about(self):
        version = '.'.join(map(str, self.params.version))
        msg = """
           <p>Клиентское приложение учётной системы.</p>
           <p>Версия %(version)s</p>
           <p>Сайт: <a href="http://snegiri.dontexist.org/projects/advisor/client/">Учётная система: Клиент</a>.</p>
           <p>Поддержка: <a href="mailto:ruslan.popov@gmail.com">Написать письмо</a>.</p>
           """ % locals()
        QMessageBox.about(self, self.tr('About application dialog'), msg.decode('utf-8'))

    def eventTraining(self):
        def callback(e_date, e_time, room_tuple, team):
            room, ok = room_tuple
            title, team_id, count, price, coach, duration = team
            begin = datetime.combine(e_date, e_time)
            duration = timedelta(minutes=int(duration * 60))

            ajax = HttpAjax(self, '/manager/cal_event_add/',
                            {'event_id': team_id,
                             'room_id': room,
                             'begin': begin,
                             'ev_type': 0}, self.session_id)
            response = ajax.parse_json()
            event_info = {'id': int(response['saved_id']),
                          'title': title, 'price': price,
                          'count': count, 'coach': coach,
                          'duration': duration,
                          'groups': self.tr('Waiting for update.')}
            eventObj = Event({}) # FIXME
            self.schedule.insertEvent(room, eventObj)

        self.dialog = DlgEventAssign('training', self)
        self.dialog.setModal(True)
        self.dialog.setCallback(callback)
        self.dialog.setModel(self.tree)
        self.dialog.setRooms(self.rooms)
        self.dialog.exec_()

    def eventRent(self):
        def callback(e_date, e_time, e_duration, room_tuple, rent):
            room, ok = room_tuple
            rent_id = rent['id']
            begin = datetime.combine(e_date, e_time)
            duration = timedelta(hours=e_duration.hour,
                                 minutes=e_duration.minute)
            params = {
                'event_id': rent_id,
                'room_id': room,
                'begin': begin,
                'ev_type': 1,
                'duration': float(duration.seconds) / 3600
                }
            ajax = HttpAjax(self, '/manager/cal_event_add/', params, self.session_id)
            response = ajax.parse_json()
            id = int(response['saved_id'])
            eventObj = Event({}) # FIXME
            self.schedule.insertEvent(room, eventObj)

        self.dialog = DlgEventAssign('rent', self)
        self.dialog.setModal(True)
        self.dialog.setCallback(callback)
        self.dialog.setRooms(self.rooms)
        self.dialog.exec_()


    def addResources(self):
        def callback(count, price):
#             ajax = HttpAjax(self, '/manager/add_resource/',
#                             {'from_date': from_range[0],
#                              'to_date': to_range[0]}, self.session_id)
            response = ajax.parse_json()
            self.statusBar().showMessage(self.tr('The week has been copied sucessfully.'))

        self.dialog = DlgAccounting(self)
        self.dialog.setModal(True)
        self.dialog.setCallback(callback)
        self.dialog.exec_()

    # Menu handlers: The end

    def makeTimer(self, handler, timeout=0, run=False):
        timer = QTimer(self)
        timer.setInterval(timeout)
        self.connect(timer, SIGNAL('timeout()'), handler)
        if run:
            timer.start()
        return timer

    def showEventProperties(self, event, index): #, room_id):
        self.dialog = EventInfo(self)
        self.dialog.setModal(True)
        self.dialog.initData(event, index)
        self.dialog.exec_()

    # Drag'n'Drop section begins
    def mousePressEvent(self, event):
        if DEBUG_COMMON:
            print 'press event', event.button()

    def mouseMoveEvent(self, event):
        if DEBUG_COMMON:
            print 'move event', event.pos()
    # Drag'n'Drop section ends


if __name__=="__main__":

    def readStyleSheet(fileName) :
        css = QString()
        file = QFile(join(dirname(__file__), fileName))
        if file.open(QIODevice.ReadOnly) :
                css = QString(file.readAll())
                file.close()
        return css

    # application global settings
    QCoreApplication.setOrganizationName('Home, Sweet Home')
    QCoreApplication.setOrganizationDomain('snegiri.dontexist.org')
    QCoreApplication.setApplicationName('Advisor Client')
    QCoreApplication.setApplicationVersion('.'.join(map(str, VERSION)))

    app = QApplication(sys.argv)
    app.setStyleSheet(readStyleSheet('manager.css'))

    # подключаем перевод
    locale = QLocale.system().name()
    print 'Locale is', locale, ':',
    tr = QTranslator()
    if tr.load('advisor-client_%s' % locale, '.'):
        print 'Translation loaded.'
        app.installTranslator(tr)
    else:
        print 'Translation not loaded.'

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

import sys, re, time
from datetime import datetime, timedelta
from os.path import dirname, join

from http import Http
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

from settings import _, DEBUG
DEBUG_COMMON, DEBUG_RFID, DEBUG_PRINTER = DEBUG

from library import ParamStorage

from PyQt4.QtGui import *
from PyQt4.QtCore import *

class MainWindow(QMainWindow):

    params = None

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)

        self.mimes = {'team': 'application/x-team-item',
                      'event':  'application/x-calendar-event',
                      }
        self.tree = []
        self.rfid_id = None

        self.params = ParamStorage() # синглтон для хранения данных
        self.params.logged_in = False
        self.params.http = Http(self)
        self.params.work_hours = (8, 24)
        self.params.quant = timedelta(minutes=30)
        self.params.multiplier = timedelta(hours=1).seconds / self.params.quant.seconds

        self.menus = []
        self.create_menus()
        self.setup_views()

        settings = QSettings()
        settings.beginGroup('network')
        host = settings.value('addressHttpServer', QVariant('WrongHost'))
        settings.endGroup()

        if 'WrongHost' == host.toString():
            self.setupApp()

        self.baseTitle = _('Manager\'s interface')
        self.logoutTitle()
        self.statusBar().showMessage(_('Ready'), 2000)
        self.resize(640, 480)

    def loggedTitle(self, response):
        last_name = response.get('last_name')
        first_name = response.get('first_name')
        if len(last_name) > 0 or len(first_name) > 0:
            self.setWindowTitle('%s : %s %s' % (self.baseTitle, last_name, first_name))
        else:
            self.setWindowTitle('%s : %s' % (self.baseTitle, response.get('username')))

    def logoutTitle(self):
        self.setWindowTitle('%s : %s' % (self.baseTitle, _('Login to start session')))

    def get_dynamic(self):
        self.bpMonday.setText(self.schedule.model().getMonday().strftime('%d/%m/%Y'))
        self.bpSunday.setText(self.schedule.model().getSunday().strftime('%d/%m/%Y'))

    def get_static(self):
        """
        Метод для получения статической информации с сервера.
        """
        if not self.params.http.request('/api/static/', 'GET', {}):
            QMessageBox.critical(self, _('Static info'), _('Unable to fetch: %s') % self.params.http.error_msg)
            return
        return self.params.http.parse()

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

    def printer_init(self, template):
        self.printer = Printer(template=template)
        run_it = True
        def show_printer_status():
            ok, tip = self.printer.get_status()
            self.printer_widget.setToolTip(tip)
            if ok:
                msg = _('Printer is ready')
            else:
                msg = _('Printer is not ready')
            self.printer_widget.setText(msg)
        self.printer_refresh = self.makeTimer(show_printer_status,
                                              self.printer.refresh_timeout,
                                              run_it)

    def prepare_filter(self, id, title):
        def handler():
            self.statusBar().showMessage(_('Filter: Room "%s" is changed its state') % title)
        return handler

    def setup_views(self):
        self.panelRooms = QHBoxLayout()

        self.schedule = QtSchedule(self)

        self.bpMonday = QLabel('--/--/----')
        self.bpSunday = QLabel('--/--/----')
        self.buttonPrev = QPushButton(_('<<'))
        self.buttonNext = QPushButton(_('>>'))
        self.buttonToday = QPushButton(_('Today'))
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
        bottomPanel.addWidget(QLabel(_('Week:')))
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

    def create_menus(self):
        """ This method generates the application menu. Usage:
        Describe the menu with all its action in data block and
        realize handlers for each action."""
        data = [
            (_('File'), [
                (_('Log in'), 'Ctrl+I', 'login', _('Start user session.')),
                (_('Log out'), '', 'logout', _('End user session.')),
                None,
                (_('Application settings'), 'Ctrl+S', 'setupApp', _('Manage the application settings.')),
                None,
                (_('Exit'), '', 'close', _('Close the application.')),
                ]
             ),
            (_('Client'), [
                (_('New'), 'Ctrl+N', 'client_new', _('Register new client.')),
                (_('Search by RFID'), 'Ctrl+D', 'client_search_rfid', _('Search a client with its RFID card.')),
                (_('Search by name'), 'Ctrl+F', 'client_search_name', _('Search a client with its name.')),
                ]
             ),
            (_('Renter'), [
                (_('New'), 'Ctrl+M', 'renter_new', _('Register new renter.')),
                (_('Search by name'), 'Ctrl+G', 'renter_search_name', _('Search a renter with its name.')),
                ]
             ),
            (_('Help'), [
                (_('About'), '', 'help_about', _('About application dialog.')),
                ]
             ),
            # 	    (_('Accounting'), [
            # 		    (_('Add resources'), '',
            # 		     'addResources', _('Add new set of resources into accounting.')),
            #                     ]
            #              ),
            ]

        for topic, info in data:
            menu = self.menuBar().addMenu(topic)
            # Disable the following menu actions, until user will be authorized.
            if not topic in (_('File'), _('Help')):
                menu.setDisabled(True)
            for item in info:
                if item is None:
                    menu.addSeparator()
                    continue
                title, short, name, desc = item
                setattr(self, 'act_%s' % name, QAction(title, self))
                action = getattr(self, 'act_%s' % name)
                action.setShortcut(short)
                action.setStatusTip(desc)
                self.connect(action, SIGNAL('triggered()'), getattr(self, name))
                menu.addAction(action)
                self.menus.append(menu)

    def interface_disable(self, state): # True = disabled, False = enabled
        # Enable menu's action
        for menu in self.menus:
            if menu.title() != _('File'):
                menu.setDisabled(state)
        # Enable the navigation buttons
        self.buttonPrev.setDisabled(state)
        self.buttonNext.setDisabled(state)
        self.buttonToday.setDisabled(state)

    def refresh_data(self):
        """ This method get the data from a server. It call periodically using timer. """

        # Do nothing until user authoruized
        if not self.params.http.is_session_open():
            return
        # Just refresh the calendar's model
        self.schedule.model().update

    # Menu handlers: The begin

    def login(self):
        def callback(credentials):
            self.credentials = credentials

        self.dialog = DlgLogin(self)
        self.dialog.setCallback(callback)
        self.dialog.setModal(True)
        dlgStatus = self.dialog.exec_()

        if QDialog.Accepted == dlgStatus:
            if not self.params.http.request('/api/login/', 'POST', self.credentials):
                QMessageBox.critical(self, _('Login'), _('Unable to login: %s') % self.params.http.error_msg)
                return

            default_response = None
            response = self.params.http.parse(default_response)
            if response and 'id' in response:
                self.params.logged_in = True
                self.loggedTitle(response)

                # подгружаем статическую информацию и список залов
                self.params.static = self.get_static()

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

                self.printer_init(template=self.params.static.get('printer'))
                self.interface_disable(False)
            else:
                QMessageBox.warning(self, _('Login failed'),
                                    _('It seems you\'ve entered wrong login/password.'))

    def logout(self):
        self.interface_disable(True)
        self.setWindowTitle('%s : %s' % (self.baseTitle, _('Login to start session')))
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

    def setupApp(self):
        self.dialog = DlgSettings(self)
        self.dialog.setModal(True)
        self.dialog.exec_()
        self.get_dynamic()
        self.params.http.reconnect()

    def client_new(self):
        self.dialog = ClientInfo(self)
        self.dialog.setModal(True)
        self.dialog.exec_()

    def client_search_rfid(self):
        """
        Метод для поиска клиента по RFID.
        """
        def callback(rfid):
            self.rfid_id = rfid

        if self.params.logged_in:
            dialog = WaitingRFID(self, mode='client', callback=callback)
            dialog.setModal(True)
            if QDialog.Accepted == dialog.exec_() and self.rfid_id:
                h = self.params.http
                if not h.request('/api/client/%s/' % self.rfid_id, 'GET', force=True):
                    QMessageBox.critical(self, _('Client info'), _('Unable to fetch: %s') % h.error_msg)
                    return
                response = h.parse()

                if 0 == len(response):
                    QMessageBox.warning(self, _('Warning'),
                                        _('This RFID belongs to nobody.'))
                else:
                    self.dialog = ClientInfo(self)
                    self.dialog.setModal(True)
                    self.dialog.initData(response[0])
                    self.dialog.exec_()
                    del(self.dialog)
                    self.rfid_id = None

    def client_search_name(self):

        def callback(user):
            self.user = user

        if self.params.logged_in:
            self.dialog = Searching(self, mode='client')
            self.dialog.setModal(True)
            self.dialog.setCallback(callback)
            if QDialog.Accepted == self.dialog.exec_():
                self.dialog = ClientInfo(self)
                self.dialog.setModal(True)
                self.dialog.initData(self.user)
                self.dialog.exec_()
                del(self.dialog)

    def renter_new(self):
        params = { 'http': self.params.http, 'static': self.static, }
        self.dialog = RenterInfo(self, params)
        self.dialog.setModal(True)
        self.dialog.exec_()

    def renter_search_name(self):
        def callback(user):
            self.user = user

        self.dialog = Searching(self, mode='renter')
        self.dialog.setModal(True)
        self.dialog.setCallback(callback)
        if QDialog.Accepted == self.dialog.exec_():
            self.dialog = RenterInfo(self)
            self.dialog.setModal(True)
            self.dialog.initData(self.user)
            self.dialog.exec_()

    def help_about(self):
        version = '.'.join(map(str, self.params.version))
        msg = """
           <p>Клиентское приложение учётной системы.</p>
           <p>Версия %(version)s</p>
           <p>Сайт: <a href="http://snegiri.dontexist.org/projects/advisor/client/">Учётная система: Клиент</a>.</p>
           <p>Поддержка: <a href="mailto:ruslan.popov@gmail.com">Написать письмо</a>.</p>
           """ % locals()
        QMessageBox.about(self, _('About application dialog'), msg.decode('utf-8'))

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
                          'groups': _('Waiting for update.')}
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
            self.statusBar().showMessage(_('The week has been copied sucessfully.'))

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
    QCoreApplication.setApplicationName('foobar')
    QCoreApplication.setApplicationVersion('0.1')

    app = QApplication(sys.argv)
    app.setStyleSheet(readStyleSheet('manager.css'))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

# -*- coding: utf-8 -*-
# (c) 2009-2012 Ruslan Popov <ruslan.popov@gmail.com>

from datetime import datetime, timedelta

from library import ParamStorage

from settings import DEBUG
DEBUG_COMMON, DEBUG_RFID, DEBUG_PRINTER = DEBUG

from PyQt4.QtGui import *
from PyQt4.QtCore import *

def dump(value):
    import pprint
    pprint.pprint(value)

class Event(object):
    """
    Модель активности для представления всех её параметров в нужном
    виде.
    """
    params = ParamStorage()

    TEAM = 0; RENT = 1;

    def __init__(self, first_day, serialized):
        self.first_day = first_day
        self.data = serialized

        self.begin = datetime.strptime(serialized.get('begin'), '%Y-%m-%d %H:%M:%S')
        self.end = datetime.strptime(serialized.get('end'), '%Y-%m-%d %H:%M:%S') + timedelta(seconds=1)
        self.duration = self.end - self.begin + timedelta(seconds=1)
        self.status = serialized.get('status')

        self.room_uuid = serialized.get('room__uuid')
        self.activity = serialized['plan']['activity']
        self.prototype = self.RENT if 'renter' in self.activity.keys() else self.TEAM

        if self.prototype == self.TEAM:
            self.styles_list = self.activity.get('dance_style')
            self.leaders = serialized.get('leaders')

    def __unicode__(self):
        return self.title

    def position(self):
        row = (self.begin.hour - self.params.work_hours[0]) * self.params.multiplier
        if self.begin.minute >= 30:
            row += 1

        # обеспечиваем пересчёт столбца с учётом сдвига окна по дням недели
        col = (self.begin.weekday() - self.first_day.weekday()) % 7

        #print '%s %s %s' % (dt, row, col)
        return (row, col)

    @property
    def uuid(self):
        return self.data.get('uuid')

    @property
    def title(self):
        if self.prototype == self.RENT:
            return QApplication.translate('event_storage', 'Rent')
        else:
            ds_list = self.activity.get('dance_style')
            return u', '.join([i.get('title') for i in ds_list])

    @property
    def category(self):
        if self.prototype == self.RENT:
            return '--'
        else:
            category = self.activity.get('category')
            return category.get('title')

    @property
    def styles(self):
        if self.prototype == self.RENT:
            return QApplication.translate('event_storage', 'Rent')
        else:
            return u', '.join(
                [i.get('title') for i in self.styles_list])

    @property
    def coaches(self):
        if self.prototype == self.RENT:
            return QApplication.translate('event_storage', 'Renter')
        else:
            return ', '.join(
                ['%s %s' % (i.get('last_name'), i.get('first_name')) \
                 for i in self.leaders])

    def set_coaches(self, values):
        self.leaders = values

    @property
    def tooltip(self):
        first_line = QApplication.translate('event_storage', '%1, %2 minutes').arg(self.title).arg(self.duration.seconds/60)
        return '%s\n%s\n%s' % (first_line, self.leaders, self.category)

    @property
    def fixed(self): #FIXME
        return int( self.data['status'] )

    def occurred(self):
        self.data['status'] = '2'

    def cancelled(self):
        self.data['status'] = '3'

class ModelStorage:
    """
    Данная модель реализует хранилище активностей.
    """
    SET = 1; GET = 2; DEL = 3

    def __init__(self):
        self.init()

    def init(self):
        self.column = None
        self.rc2e = {} # (row, col, room): event
        self.e2rc = {} # (event, room): [(row, col), (row, col), ...]

    def dump(self):
        dump(self.rc2e)
        dump(self.e2rc)

    def setFilter(self, column):
        self.column = column

    def searchByID(self, event_uuid):
        for event, room in self.e2rc.keys():
            if event.uuid == event_uuid:
                return event
        return None

    def byRCR(self, op, key, value=None):
        """
        Метод для создания, изменения или удаления элементов хранилища
        по ключу RCR (Row, Column, Room).

        @type  op: SET, GET, DEL
        @param op: Оператор, определяющий действие над элементов хранилища.
        @type  key: tuple
        @param key: Ключ элемента виде (Row, Column, Room).
        @type  value: *
        @param value: Значение для сохранения, имеет смысл только для операции SET.
        """
        if self.column is not None:
            row, column, room_id = key
            key = (row, column + self.column, room_id)
        if op == self.SET:
            return self.rc2e.update( { key: value } )
        elif op == self.GET:
            return self.rc2e.get(key)
        elif op == self.DEL:
            del(self.rc2e[key])
        else:
            raise QApplication.translate('event_storage', 'ModelStorage: Unknown operation')

    def getByER(self, key):
        cells = self.e2rc.get(key, None)
        if self.column is not None:
            result = []
            for row, column in cells:
                result.append((row, column - self.column))
            cells = result
        return cells

    def setByER(self, key, value):
        self.e2rc.update( { key: value } )

    def delByER(self, key):
        del(self.e2rc[key])

class EventStorage(QAbstractTableModel):
    """
    Класс реализации модели хранилища событий.
    """
    params = ParamStorage()

    def __init__(self, parent, mode='week', use_window=False):
        QAbstractTableModel.__init__(self, parent)

        self.parent = parent
        self.mode = mode
        self.one_day_mode = None

        if 'week' == self.mode:
            self.week_days = self.params.WEEK_DAYS
        else:
            self.week_days = [ self.tr('Day') ]

        # вычисляем параметры модели: количество рядов и ячеек
        begin_hour, end_hour = self.params.work_hours
        self.rows_count = (end_hour - begin_hour) * self.params.multiplier
        self.cols_count = len(self.week_days)

        # два режима работы, оконный (плавающее окно по датам) и понедельный (ПН-ВС)
        if use_window:
            self.weekRange = (datetime.now().date() - timedelta(days=1), datetime.now().date() + timedelta(days=5))
        else:
            self.weekRange = self.date2range(datetime.now())

        # NOT USED YET: self.getMime = parent.getMime

        # Item storage
        self.storage = ModelStorage()
        self.storage_init()

    def storage_init(self):
        """Инициализирует хранилище."""
        self.emit(SIGNAL('layoutAboutToBeChanged()'))
        self.storage.init()
        self.emit(SIGNAL('layoutChanged()'))

    def update(self):
        """Обновляет хранилище."""
        if 'week' == self.mode:
            self.load_data(*self.weekRange)

    def insert(self, room_uuid, event, emit_signal=False):
        """Добавляет новое событие в хранилище."""
        if emit_signal:
            self.emit(SIGNAL('layoutAboutToBeChanged()'))

        row, col = event.position()
        cells = []
        for i in xrange(event.duration.seconds / self.params.quant.seconds):
            cells.append( (row + i, col) )
            self.storage.byRCR(ModelStorage.SET,
                               (row + i, col, room_uuid), event)
        self.storage.setByER( (event, room_uuid), cells )

        if emit_signal:
            self.emit(SIGNAL('layoutChanged()'))

    def remove(self, event, index, emit_signal=False):
        """Удаляет событие из хранилища."""
        room = event.data['room']['id']
        cell_list = self.get_cells_by_event(event, room)
        if cell_list:
            for row, col in cell_list:
                self.storage.byRCR(ModelStorage.DEL,
                                   (row, col, room))
            self.storage.delByER( (event, room) )
            if emit_signal and index:
                self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'), index, index)

    def change(self, event, index):
        """ Change event's info."""
        self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'), index, index)

    def move(self, row, col, room, event):
        """ This method moves the event to new cell. """
        self.remove(event, room)
        self.insert(row, col, room, event)

    def load_data(self, first_day, last_day):
        """
        Метод обеспечивает загрузку информации о событиях в календарь.

        @type  first_day: date
        @param first_day: Первый день периода включительно.
        @type  last_day: date
        @param last_day: Последний день периода включительно.

        @rtype: boolean
        @return: Результат загрузки.
        """
        if 'day' == self.mode:
            return False

        self.parent.parent.statusBar().showMessage(self.tr('Request information for the calendar.')) # fixme: msg queue

        http = self.params.http
        if http and http.is_session_open():
            http.request('/api/calendar/%s/' % first_day.strftime('%d%m%Y'), 'GET', {}) # FIXME: wrong place for HTTP Request!
            self.parent.parent.statusBar().showMessage(self.tr('Parsing the response...'))
            response = http.parse(None)

            # result processing
            if response:
                self.parent.parent.statusBar().showMessage(self.tr('Filling the calendar...'))
                self.storage_init()
                # place the event in the model
                for item in response:
                    qApp.processEvents() # keep GUI active
                    event = Event(first_day, item)
                    self.insert(event.room_uuid, event)
                # draw events
                self.emit(SIGNAL('layoutChanged()'))
                self.parent.parent.statusBar().showMessage(self.tr('Done'), 2000)
                # debugging
                #self.storage.dump()
                return True
            else:
                self.parent.parent.statusBar().showMessage(self.tr('No reply'))
                return False

    def rowCount(self, parent): # protected
        if parent.isValid():
            return 0
        else:
            return self.rows_count

    def columnCount(self, parent): # protected
        if parent.isValid():
            return 0
        else:
            if 'week' == self.mode:
                return self.cols_count
            else:
                return 1

    def getShowMode(self):
        return self.mode

    def changeShowMode(self, column):
        if 'week' == self.mode:
            self.mode = 'day'
            self.storage.setFilter(column)
            self.one_day_mode = self.weekRange[0] + timedelta(days=column)
        else:
            self.mode = 'week'
            self.storage.setFilter(None)
            self.one_day_mode = None
        self.emit(SIGNAL('layoutChanged()'))

    def colByMode(self, column):
        if self.mode == 'week':
            return column
        else:
            return self.dayColumn

    def exchangeRoom(self, data_a, data_b):
        room_a = data_a[2]
        room_b = data_b[2]
        # events data
        event_a = self.storage.byRCR(ModelStorage.GET, data_a)
        event_b = self.storage.byRCR(ModelStorage.GET, data_b)
        # get cells list for each event
        items_a = self.storage.getByER( (event_a, room_a) )
        items_b = self.storage.getByER( (event_b, room_b) )
        # remove all records for each event
        self.remove(event_a, room_a)
        self.remove(event_b, room_b)
        # chech the exchange ability
        if self.may_insert(event_a, room_b) and \
                self.may_insert(event_b, room_a):
            # send the information to the server
            params = {'id_a': event_a.id,
                      'id_b': event_b.id}
            ajax = HttpAjax(self.parent, '/manager/exchange_room/',
                            params, self.parent.session_id)
            if ajax:
                response = ajax.parse_json()
                if response is not None:
                    # add events, exchanging rooms
                    self.insert(room_a, event_b)
                    self.insert(room_b, event_a)
                    self.emit(SIGNAL('layoutChanged()'))
                    return True
        # get back
        self.insert(room_a, event_a)
        self.insert(room_b, event_b)
        self.emit(SIGNAL('layoutChanged()'))
        return False

    def showCurrWeek(self):
        if 'week' == self.mode:
            now = datetime.now()
            self.load_data(*self.weekRange)
            return self.weekRange
        else:
            return None

    def showPrevWeek(self):
        if 'week' == self.mode:
            current_monday, current_sunday = self.weekRange
            prev_monday = current_monday - timedelta(days=7)
            prev_sunday = current_sunday - timedelta(days=7)
            self.weekRange = (prev_monday, prev_sunday)
            self.load_data(*self.weekRange)
            return self.weekRange
        else:
            return None

    def showNextWeek(self):
        if 'week' == self.mode:
            current_monday, current_sunday = self.weekRange
            next_monday = current_monday + timedelta(days=7)
            next_sunday = current_sunday + timedelta(days=7)
            self.weekRange = (next_monday, next_sunday)
            self.load_data(*self.weekRange)
            return self.weekRange
        else:
            return None

    def headerData(self, section, orientation, role):
        """
        Метод отображения заголовков для полей модели.
        """
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            first_day, last_dat = self.weekRange

            if 'week' == self.mode:
                delta = section
            else:
                delta = self.storage.column

            day = first_day + timedelta(days=delta)
            day_str = day.strftime('%d/%m')
            return QVariant('%s\n%s' % (self.week_days[day.weekday()], day_str))

        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            begin_hour, end_hour = self.params.work_hours
            start = timedelta(hours=begin_hour)
            step = timedelta(seconds=(self.params.quant.seconds * section))
            return QVariant(str(start + step)[:-3])
        return QVariant()

    def data(self, index, role, room_id=None):
        """ This method returns the data from model. Parameter 'role' here means room. """
        if not index.isValid() or not room_id:
            return QVariant()
        if role not in (Qt.DisplayRole, Qt.ToolTipRole):
            return QVariant()
        row = index.row()
        col = index.column()
        event = self.get_event_by_cell(row, col, room_id)
        if event:
            if role == Qt.ToolTipRole:
                return QVariant( event.tooltip )
            if role == Qt.DisplayRole:
                cells = self.get_cells_by_event(event, room_id)
                if cells:
                    if cells[0] == (row, col):
                        event.show_type = 'head'
                    elif cells[-1] == (row, col):
                        event.show_type = 'tail'
                    else:
                        event.show_type = 'body'
                return QVariant(event)
        return QVariant()

    def getMonday(self):
        return self.weekRange[0]

    def getSunday(self):
        return self.weekRange[1]

    def get_event_by_cell(self, row, col, room_id):
        """ This methods returns the event by given coordinates. """
        return self.storage.byRCR(ModelStorage.GET, (row, col, room_id))

    def get_cells_by_event(self, event, room_id):
        """ This method returns the cells list for given event. """
        return self.storage.getByER( (event, room_id) )

    def date2range(self, dt):
        """ This methods returns the day rango for a given week. """
        if type(dt) is datetime:
            dt = dt.date()
        monday = dt - timedelta(days=dt.weekday())
        sunday = monday + timedelta(days=6)
        return (monday, sunday)

    def may_insert(self, event, room_id):
        """ This method checks the ability of placing the event on schedule. """
        row, col = self.datetime2rowcol(event.begin)
        for i in xrange(event.duration.seconds / self.params.quant.seconds):
            if self.storage.byRCR(
                ModelStorage.GET,
                (row + i, col, room_id)
                ) is not None:
                return False
        return True

#     def prepare_event_cells(self, event, room_id, row, col):
#         cells = []
#         for i in xrange(event.duration.seconds / self.params.quant.seconds):
#             cells.append( (row + i, col, room_id) )
#         return cells

#     def get_free_rooms(self, event, row, col):
#         """ Метод для проверки возможности размещения события по указанным
#         координатам. Возвращает список залов, которые предоставляют такую
#         возможность.

#         Для каждого зала из списка проверить наличие свободных
#         интервалов времени.
#         """
#         result = []
#         for room_name, room_color, room_id in self.rooms:
#             free = []
#             for i in xrange(event.duration.seconds / self.params.quant.seconds):
#                 free.append( self.rc2e.get( (row + i, col, room_id), None ) is None )
#             print free

#             if reduce( lambda x,y: x and y, free ):
#                 result.append(room_id)
#         return result

    # DnD support - the begin

    def supportedDropActions(self):
        """ This method defines the actions supported by this model. """
        if DEBUG_COMMON:
            print 'EventStorage::supportedDropActions'
        return (Qt.CopyAction | Qt.MoveAction)

    def flags(self, index):
        """ This method defines the list of items that may in DnD operations. """
        #if DEBUG_COMMON:
        #    print 'EventStorage::flags', index.row(), index.column()
        if index.isValid():
            res = (Qt.ItemIsEnabled | Qt.ItemIsSelectable
                   | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
        else:
            res = (Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
        return res

    def mimeTypes(self):
        """ This method declares supported MIME types. """
        types = QStringList()
        types << self.getMime('event') << self.getMime('team')
        return types

    def mimeData(self, indexes):
        """ This method converts objects into supported MIME format. """
        mimeData = QMimeData()
        encodedData = QByteArray()

        stream = QDataStream(encodedData, QIODevice.WriteOnly)

        events = []

        if DEBUG_COMMON:
            print indexes

            for index in indexes:
                if index.isValid():
                    print dir(index)
                    print self.data(index, 100)

        mimeData.setData(self.getMime('event'), encodedData)
        return mimeData

    def dropMimeData(self, data, action, row, column, parent):
        if action == Qt.IgnoreAction:
            return True

        event_mime = self.getMime('event')
        team_mime = self.getMime('team')

        if not data.hasFormat(event_mime) and \
                not data.hasFormat(team_mime):
            return False
        if column > 0:
            return False

        itemData = data.data(event_mime)
        dataStream = QDataStream(itemData, QIODevice.ReadOnly)

        id = QString()
        stream >> id

        return True

    def setData(self, index, value, role):
        """ Parameter 'role' means room. """
        return True

    def setHeaderData(self, section, orientation, value, role):
        return True

#     def removeRows(self, row, count, parent):
#         print 'EventStorage::removeRows'
#         if parent.isValid():
#             return False

#         self.beginRemoveRows(parent, row, row)
#         # remove here
#         self.endRemoveRows()
#         return True

#     def insertRows(self, row, count, parent):
#         print 'EventStorage::insertRows'

    # DnD support - the end


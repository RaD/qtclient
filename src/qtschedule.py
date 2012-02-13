# -*- coding: utf-8 -*-
# (c) 2009-2010 Ruslan Popov <ruslan.popov@gmail.com>

import sys, re
from datetime import datetime, timedelta

from library import ParamStorage
from event_storage import EventStorage
from dlg_settings import TabGeneral


from PyQt4.QtGui import *
from PyQt4.QtCore import *

class QtSchedule(QTableView):

    """ Calendar class. """

    params = ParamStorage()

    def __init__(self, parent):
        QTableView.__init__(self, parent)

        self.parent = parent

        # Define the model
        self.model_object = EventStorage(self, mode='week', use_window=True)
        self.setModel(self.model_object)

        # Define the cell delegate
        delegate = QtScheduleDelegate(self)
        self.setItemDelegate(delegate)

        self.events = {}
        self.cells = {}
        self.scrolledCellX = 0
        self.scrolledCellY = 0

        self.getMime = parent.getMime

        self.current_event = None
        self.current_data = None
        self.selected_event = None
        self.selected_data = None

        # Deny to select mutiple cells
        self.setSelectionMode(QAbstractItemView.NoSelection) #SingleSelection)

        # Allow DnD
#         self.setAcceptDrops(True)
#         self.setDragEnabled(True)
#         self.setDropIndicatorShown(True)

        #self.setDragDropMode(QAbstractItemView.DragDrop) #InternalMove

        # Deny to resize cells
        self.verticalHeader().setResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().setResizeMode(QHeaderView.Stretch)
        self.connect(self.horizontalHeader(),
                     SIGNAL('sectionClicked(int)'),
                     self.expandDay)

        # Set scrolling
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        self.setGridStyle(Qt.DotLine)
        self.setShowGrid(True)

        self.resizeColumnsToContents()
        self.verticalHeader().setStretchLastSection(True)

        # Context menu
        self.ctxMenuExchange = QAction(self.tr('Exchange rooms'), self)
        self.ctxMenuExchange.setStatusTip(self.tr('Exchange rooms between selected and current events.'))
        self.connect(self.ctxMenuExchange, SIGNAL('triggered()'), self.exchangeRooms)
        self.contextMenu = QMenu(self)
        self.contextMenu.addAction(self.ctxMenuExchange)

    # def update_static(self, params=dict()):
    #     """ params = {'rooms',} """
    #     self.rooms = params.get('rooms', tuple())
    #     self.model().rooms = self.params.rooms

    def string2color(self, color):
        """ This method converts #RRGGBB into QColor. """

        regexp = re.compile(r'#(?P<red_component>[0-9a-fA-F]{2})(?P<green_component>[0-9a-fA-F]{2})(?P<blue_component>[0-9a-fA-F]{2})')
        groups = re.match(regexp, color)
        if groups:
            return QColor(int(groups.group('red_component'), 16),
                          int(groups.group('green_component'), 16),
                          int(groups.group('blue_component'), 16))
        return None

    def get_scrolled_coords(self, rel_x, rel_y):
        """ This method calculates absolute coordinates using relative
        coordinates and scroller position."""
        abs_x = rel_x - self.scrolledCellX
        abs_y = rel_y - self.scrolledCellY
        return (abs_x, abs_y)

    def get_cell_coords(self, abs_x, abs_y):
        """ This method defines which cell (row, col) contains of the given coordinates. """
        return (self.rowAt(abs_y), self.columnAt(abs_x))

    def insertEvent(self, room_id, event):
        """
        Метод для добавления события в календарь.
        """
        self.model().insert(room_id, event, True)

    def cellRowColRelative(self, rel):
        """ This method defines which cell contains of the given
        coordinates, take in view the scroller position."""
        if type(rel) is tuple:
            rel_x, rel_y = rel
            abs_x = rel_x - self.scrolledCellX
            abs_y = rel_y - self.scrolledCellY
        elif type(rel) is QPoint:
            abs_x = rel.x() - self.scrolledCellX
            abs_y = rel.y() - self.scrolledCellY
        return (self.rowAt(abs_y), self.columnAt(abs_x))

    def emptyRoomAt(self, (row_col)):
        """ This method returns the list of free rooms at the given cells. """
        row, col = row_col
        free = []
        for item in self.params.static.get('rooms'):
            room_id = item.get('uuid')
            event = self.model().get_event_by_cell(row, col, room_id)
            if not event:
                free.append(id) #wtf?
        return free

    def scrollContentsBy(self, dx, dy):
        """ Scrolling handler, see QAbstractScrollArea. Accumulate
        scrolling for each axe in pixels."""
        # see. QAbstractItemView.ScrollMode
        if dx != 0:
            self.scrolledCellX += dx
        if dy != 0:
            self.scrolledCellY += dy
        QTableView.scrollContentsBy(self, dx, dy)

    def expandDay(self, section):
        self.model().changeShowMode(section)
        self.horizontalHeader().setResizeMode(QHeaderView.Stretch)

    def data_of_event(self, event):
        """ This method returns the event's information. """
        index = self.indexAt(event.pos())
        row = index.row()
        col = index.column()
        x = event.x() - self.scrolledCellX
        y = event.y() - self.scrolledCellY
        w = self.columnWidth(index.column())
        cx, cy = self.get_scrolled_coords(self.columnViewportPosition(col),
                                          self.rowViewportPosition(row))
        rooms = self.params.static.get('rooms')
        event_index = (x - cx) / (w / len(rooms))
        room = rooms[event_index]
        return (index, row, col, x, y, cx, cy,
                room.get('title'), room.get('color'), room.get('uuid'))

    def event_intersection(self, event_a, event_b):
        """ This method check the events intersection by time. """
        a1 = event_a.begin
        a2 = a1 + event_a.duration
        b1 = event_b.begin
        b2 = b1 + event_b.duration

        if a1 <= b1 < a2 <= b2:
            return True
        if b1 <= a1 < b2 <= a2:
            return True
        if a1 <= b1 < b2 <= a2:
            return True
        if b1 <= a1 < a2 <= b2:
            return True
        return False

    def contextMenuEvent(self, event):
        """ Context menu's handler. """
        index, row, col, x, y, cx, cy,\
            room_name, room_color, room_id \
            = self.data_of_event(event)

        # Check an event existence at the given cell.
        self.current_event = self.model().get_event_by_cell(row, col, room_id)
        self.current_data = (row, col, room_id)
        if not self.current_event:
            return
        else:
            # keep the current event
            self.contextRow = index.row()

            self.ctxMenuExchange.setDisabled(False)

            # deny change if:
            # - only one event is choosen;
            # - events' dates do not equal;
            # - date of any event is in past
            if self.selected_event is None or \
                    not self.event_intersection(self.current_event, self.selected_event) or \
                    self.current_event == self.selected_event or \
                    self.current_event.begin.date() != self.selected_event.begin.date() or \
                    self.current_event.begin < datetime.now() or \
                    self.selected_event.begin < datetime.now():
                self.ctxMenuExchange.setDisabled(True)
            if 'week' != self.model().getShowMode:
                self.ctxMenuExchange.setDisabled(True)
            self.contextMenu.exec_(event.globalPos())

    def exchangeRooms(self):
        exchanged = self.model().exchangeRoom(self.current_data,
                                              self.selected_data)
        if exchanged:
            data = self.current_data
            self.current_data = self.selected_data
            self.selected_data = data
            self.parent.statusBar().showMessage(self.tr('Complete.'))
        else:
            self.parent.statusBar().showMessage(self.tr('Unable to exchange.'))

    def mousePressEvent(self, event):
        """ Mouse click handler. Do DnD here. """
        if not self.params.logged_in:
            return
        if event.button() == Qt.LeftButton:
            index, row, col, x, y, cx, cy,\
                room_name, room_color, room_id \
                = self.data_of_event(event)

            # Check an event existence in the given cell.
            self.current_event = self.model().get_event_by_cell(row, col, room_id)
            if not self.current_event:
                return
            else:
                # Select choosen event
                self.selected_event = self.current_event
                self.selected_data = (row, col, room_id)
                self.model().emit(SIGNAL('layoutChanged()'))

            pixmap = QPixmap(100, 60)
            pixmap.fill(Qt.white)
            painter = QPainter(pixmap)
            painter.fillRect(2,2,96,56, self.string2color(room_color))

            pen = QPen(Qt.black)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(0, 0, 100, 60)

            painter.end()

            itemData = QByteArray()
            dataStream = QDataStream(itemData, QIODevice.WriteOnly)
            dataStream << QString('%i,%i,%s' % (row, col, room_id))
            mimeData = QMimeData()
            mimeData.setData(self.getMime('event'), itemData)

            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.setPixmap(pixmap)

            drop_action = {
                0: 'Qt::IgnoreAction',
                1: 'Qt::CopyAction',
                2: 'Qt::MoveAction',
                4: 'Qt::LinkAction',
                255: 'Qt::ActionMask',
                }

            #res = drag.start(Qt.CopyAction|Qt.MoveAction)
            #print 'QtSchedule::mousePressEvent', drop_action[res]

    def mouseDoubleClickEvent(self, event):
        index = self.indexAt(event.pos())
        row = index.row()
        col = index.column()
        x = event.x() - self.scrolledCellX
        y = event.y() - self.scrolledCellY
        w = self.columnWidth(col)
        cx, cy = self.get_scrolled_coords(self.columnViewportPosition(col),
                                          self.rowViewportPosition(row))
        rooms = self.params.static.get('rooms')
        event_index = (x - cx) / (w / len(rooms))
        room = rooms[event_index]
        model = self.model()
        variant = model.data(model.index(row, col), Qt.DisplayRole, room.get('uuid'))
        if not variant.isValid():
            return
        evt = variant.toPyObject()
        self.parent.showEventProperties(evt, index) #, room_id)
        event.accept()

    def mouseMoveEvent(self, event):
        pass

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.getMime('event')) or \
                event.mimeData().hasFormat(self.getMime('team')):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """ This method is called while DnD. Here it needs to do the
        check for dropping ability on current cell."""
        drop_cell = self.cellRowColRelative(event.pos())
        free_rooms = self.emptyRoomAt(drop_cell)

        if len(free_rooms) > 0:
            QTableView.dragMoveEvent(self, event)
            if event.mimeData().hasFormat(self.getMime('event')) or \
                    event.mimeData().hasFormat(self.getMime('team')):
                event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        event_mime = self.getMime('event')
        team_mime = self.getMime('team')
        if event.mimeData().hasFormat(event_mime):
            itemData = event.mimeData().data(event_mime)
            dataStream = QDataStream(itemData, QIODevice.ReadOnly)
            coordinates = QString()
            dataStream >> coordinates
            (row, col, room_id) = [int(i) for i in coordinates.split(',')]

            event.acceptProposedAction()
            drop_cell = self.cellRowColRelative(event.pos())

        elif event.mimeData().hasFormat(team_mime):
            itemData = event.mimeData().data(team_mime)
            dataStream = QDataStream(itemData, QIODevice.ReadOnly)
            team = QString()
            dataStream >> team

            event.acceptProposedAction()

        else:
            event.ignore()

    def viewportEvent(self, event):
        """ Reimplement ToolTip Event. """
        if self.params.logged_in:
            rooms = self.params.static.get('rooms')
            if event.type() == QEvent.ToolTip and rooms:
                help = QHelpEvent(event)
                index = self.indexAt(help.pos())
                row = index.row()
                col = index.column()
                x = help.x() - self.scrolledCellX
                y = help.y() - self.scrolledCellY
                w = self.columnWidth(col)
                cx, cy = self.get_scrolled_coords(self.columnViewportPosition(col),
                                                  self.rowViewportPosition(row))
                event_index = (x - cx) / (w / len(rooms))

                try:
                    room = rooms[event_index]
                except IndexError:
                    print rooms
                    print event_index
                    room = rooms[0]

                model = self.model()
                tooltip = model.data(model.index(row, col), Qt.ToolTipRole, room.get('uuid')).toString()
                if len(tooltip) > 0:
                    QToolTip.showText(help.globalPos(), QString(tooltip))
        return QTableView.viewportEvent(self, event)

#from settings import XPM_EVENT_CLOSED

from event_storage import Event

class QtScheduleDelegate(QItemDelegate):

    """ The delegate for scheduler's cells. """

    DEBUG = True
    HORIZONTAL = 0
    VERTICAL = 1
    PADDING = 2
    STEP = 5

    params = ParamStorage()

    def __init__(self, parent=None):
        QItemDelegate.__init__(self, parent)
        self.parent = parent # указатель на QtSchedule

        self.settings = QSettings()
        general = TabGeneral(self.parent)
        general.loadSettings(self.settings)
        width = general.borderWidth.text()
        self.borderWidth = int(width)
        color = general.borderColor_value
        self.borderColor = color

    def debug(self, msg):
        if self.DEBUG:
            print '[QtScheduleDelegate] %s' % msg

    def prepare(self, painter, pen_tuple, brush=None):
        pen_color, pen_width = pen_tuple
        pen = QPen(pen_color)
        pen.setWidth(pen_width)
        painter.setPen(pen)
        if brush is not None:
            brush_color = brush
            brush = QBrush(brush_color)
            painter.setBrush(brush)

    def paint(self, painter, cell, index):
        """ This method draws the cell. """
        if not self.params.logged_in:
            return

        painter.save()

        model = index.model()
        rooms = self.params.static.get('rooms')
        room_count = len(rooms)

        height = cell.rect.height()
        width = cell.rect.width()

        row = index.row()
        col = index.column()

        dx = col * (width + 1) #self.parent.scrolledCellX
        dy = self.parent.scrolledCellY + row * (height + 1)

        pen_width = 1

        for room in rooms:
            event = model.data(index, Qt.DisplayRole, room.get('uuid')).toPyObject()

            if isinstance(event, Event):
                # fill the event's body
                if self.parent.showGrid():
                    w = (width - pen_width)/ room_count
                else:
                    w = width / room_count

                x = dx + w * map(lambda x: x == room, rooms).index(True)
                y = dy

                painter.fillRect(x, y, w, height, self.parent.string2color(room.get('color')));

                if event.show_type == 'tail':
                    if event.fixed in (2, 3):
                        if event.fixed == 2:
                            self.prepare( painter, (Qt.green, 3) )
                        if event.fixed == 3:
                            self.prepare( painter, (Qt.blue, 3) )
                        painter.drawLine(x+self.PADDING, y+height-self.PADDING-5,
                                         x+self.PADDING+5, y+height-self.PADDING)

                line_dir = self.direction(w, height)

                # prepare to draw the borders
                if self.parent.selected_event == event:
                    self.prepare( painter, (self.borderColor, self.borderWidth) )
                else:
                    self.prepare( painter, (Qt.black, pen_width) )

                # draws items using type of the cell
                painter.drawLine(x, y+height, x, y)
                painter.drawLine(x+w, y+height, x+w, y)
                if event.show_type == 'head':
                    painter.drawLine(x, y, x+w, y)

                    # draw event's title
                    self.prepare( painter, (Qt.black, pen_width) )
                    painter.drawText(x+1, y+1, w-2, height-2,
                                     Qt.AlignLeft | Qt.AlignTop,
                                     event.title)

                elif event.show_type == 'tail':
                    painter.drawLine(x, y+height, x+w, y+height)

                    # draw event's coach
                    self.prepare( painter, (Qt.black, pen_width) )
                    painter.drawText(x+1, y+1, w-2, height-2,
                                     Qt.AlignLeft | Qt.AlignTop,
                                     event.coaches)
                else:
                    pass

        self.timeline(model, painter, dx, dy, col, row, width, height, pen_width)

        painter.restore()
        #QItemDelegate.paint(self, painter, cell, index)

    def timeline(self, model, painter, dx, dy, col, row, width, height, pen_width):
        """
        Метод для отрисовки линии текущего времени.
        """
        now = datetime.now()
        first_day, last_day = model.weekRange

        _row = _col = None
        if model.mode == 'week':
            if first_day <= now.date() <= last_day:
                _col = (now.weekday() - first_day.weekday()) % 7
        else:
            if now.date() == model.one_day_mode:
                _col = 0

        if col == _col:
            _row = (now.hour - self.params.work_hours[0]) * self.params.multiplier
            if now.minute >= 30:
                _row += 1
            if row == _row:
                x1 = dx
                y1 = dy + (now.minute % 30) * height / 30
                x2 = x1 + width
                y2 = y1

                for i in ((Qt.black, pen_width+2), (Qt.red, pen_width)):
                    self.prepare( painter, i )
                    painter.drawLine(x1, y1, x2, y2)

    def direction(self, width, height):
        return self.HORIZONTAL if width < height else self.VERTICAL

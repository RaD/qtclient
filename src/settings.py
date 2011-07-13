# -*- coding: utf-8 -*-
# (c) 2009-2010 Ruslan Popov <ruslan.popov@gmail.com>

from PyQt4.QtCore import *

DEBUG = (True, True, True) # Common, RFID, Printer

TEST_CREDENTIALS = {'login': 'rad', 'password': 'q1'}

userRoles = {
    'getObjectID': Qt.UserRole,
}

import gettext
from os.path import dirname, join
gettext.bindtextdomain('project', join(dirname(__file__), 'locale'))
gettext.textdomain('project')
_ = lambda a: unicode(gettext.gettext(a), 'utf8')

PORT = {
    'name': '/dev/ttyUSB0',
    'rate': 38400,
    'bits_in_byte': 7,
    'parity': 'N',
    'stop_bits': 2
    }

SCHEDULE_REFRESH_TIMEOUT = 60000 # one minute
PRINTER_REFRESH_TIMEOUT = 10000 # ten seconds

MODEL_PROPERTIES = {
    'INFLOW': '0',
    'OUTFLOW': '1',
    'TYPE_RFIDCARDS': '0',
    }

WEEK_DAYS = [ _('Monday'), _('Tuesday'),
              _('Wednesday'), _('Thursday'),
              _('Friday'), _('Saturday'),
              _('Sunday') ]

XPM_EVENT_CLOSED = [
    '8 8 4 1',
    '+ c #000000',
    '. c #FFFFFF',
    '* c #FF0000',
    '= c #FF8888',
    '++++++++',
    '+.....*+',
    '+....*=+',
    '+....*=+',
    '+*=.*=.+',
    '+.*=*=.+',
    '+..*=..+',
    '++++++++',
    ]

# -*- coding: utf-8 -*-
# (c) 2009-2010 Ruslan Popov <ruslan.popov@gmail.com>

from PyQt4.QtCore import *

DEBUG = (True, True, False) # Common, RFID, Printer
VERSION = (0, 4, 2)

TEST_CREDENTIALS = {'login': 'rad', 'password': 'q1'}

userRoles = {
    'getObjectID': Qt.UserRole,
}

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

# -*- coding: utf-8 -*-
# (c) 2012 Ruslan Popov <ruslan.popov@gmail.com>

u"""
Модуль для тестирования GUI клиента.
"""

__author__ = "Ruslan Popov <ruslan.popov@gmail.com>"

import sys
import unittest

from PyQt4.QtGui import QApplication
from PyQt4.QtTest import QTest
from PyQt4.QtCore import Qt, QSettings, QVariant

from manager import MainWindow
from dlg_login import DlgLogin

class ManagerTest(unittest.TestCase):

    def setUp(self):
        u"""Настройка тестовой среды."""
        self.app = QApplication(sys.argv)
        self.setSettings()
        self.wnd = MainWindow()
        self.makeLogin('rad', 'q1')

    def setSettings(self):
        self.settings = QSettings()
        general = dict(
            debug_app=True,
            debug_use_ssl=False,
            debug_reader=True,
            debug_printer=True)
        network = dict(
            addressHttpServer='localhost',
            portHttpServer='8000',
            useProxy=False)
        printer = dict(device_file='/dev/usblp0')
        self.settingsGroup('general', general)
        self.settingsGroup('network', network)
        self.settingsGroup('printer', printer)

    def settingsGroup(self, group, params):
        self.settings.beginGroup(group)
        for key, value in params.items():
            self.settings.setValue(key, QVariant(value))
        self.settings.endGroup()

    def makeLogin(self, login, password):
        dialog = DlgLogin(None, connecting_to=u'localhost/test')
        dialog.editLogin.setText(login)
        dialog.editPassword.setText(password)
        QTest.mouseClick(dialog.buttonOk, Qt.LeftButton)
        status, data = dialog.response
        assert status == 'ALL_OK'
        assert isinstance(data, dict)
        assert login == data.get('username')

    def test_setup(self):
        """Тестирование настройки приложения."""
        # self.form.app_settings()
        # cancel_button = self.form.dialog.cancelButton
        # QTest.mouseClick(cancel_button, Qt.LeftButton)



if __name__ == "__main__":
    unittest.main()

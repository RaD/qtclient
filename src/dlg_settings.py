# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from ui_dialog import UiDlgTemplate

from PyQt4.QtGui import *
from PyQt4.QtCore import *

class DlgSettings(QDialog):
    """
    Класс диалога настроек приложения.
    """

    def __init__(self, parent=None):
        """
        Конструктор диалога.
        """
        QDialog.__init__(self, parent)

        self.parent = parent

        # определяем вкладки диалога
        self.tabWidget = QTabWidget()
        self.tabWidget.addTab(TabGeneral(self), self.tr('General'))
        self.tabWidget.addTab(TabNetwork(self), self.tr('Network'))
        self.tabWidget.addTab(TabPrinter(self), self.tr('Printer'))
        # и их последовательность
        self.tabIndex = ['general', 'network', 'printer']

        applyButton = QPushButton(self.tr('Apply'))
        self.cancelButton = QPushButton(self.tr('Cancel'))

        self.connect(applyButton, SIGNAL('clicked()'),
                     self.applyDialog)
        self.connect(self.cancelButton, SIGNAL('clicked()'),
                     self, SLOT('reject()'))

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(applyButton)
        buttonLayout.addWidget(self.cancelButton)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tabWidget)
        mainLayout.addLayout(buttonLayout)
        self.setLayout(mainLayout)

        self.setWindowTitle(self.tr('Settings'))

        # подгружаем настройки
        self.settings = QSettings()
        self.loadSettings()

    def applyDialog(self):
        """
        Метод для применения диалога.
        """
        self.saveSettings()
        self.accept()

    def loadSettings(self):
        """
        Метод загрузки настроек в диалог.
        """
        for index in xrange(self.tabWidget.count()):
            tab = self.tabWidget.widget(index)
            tab.loadSettings(self.settings)

    def saveSettings(self):
        """
        Метод сохранения настроек из диалога.
        """
        for index in xrange(self.tabWidget.count()):
            tab = self.tabWidget.widget(index)
            tab.saveSettings(self.settings)

class TabAbstract(QWidget):
    """
    Класс абстрактной вкладки диалога.

    Предоставляет методы загрузки и сохранения настроек из вкладок
    диалога.

    Каждый класс вкладки должен определять атрибут defaults (словарь),
    в котором описаны поля и их значения по умолчанию.
    """
    def __init__(self, parent=None):
        self.parent = parent

    def saveSettings(self, settings):
        """
        Метод сохранения настроек из вкладки диалога.
        """
        is_changed = False
        settings.beginGroup(self.groupName)
        for name in self.defaults.keys():
            field = getattr(self, name)

            if type(field) is QLineEdit:
                value = field.text()
            elif type(field) is QCheckBox:
                value = field.isChecked()
            elif type(field) is QSpinBox:
                value = field.value()
            elif type(field) is QToolButton:
                value = self.borderColor_value.name()

            original_value = self.defaults[name]
            if original_value != value:
                is_changed = True
            settings.setValue(name, QVariant(value))
        settings.endGroup()
        return is_changed

    def loadSettings(self, settings):
        """
        Метод загрузки настроек во вкладку диалога.
        """
        settings.beginGroup(self.groupName)
        for name in self.defaults.keys():
            field = getattr(self, name)
            raw_value = settings.value(name, QVariant(self.defaults[name]))
            if type(field) is QLineEdit:
                value = raw_value.toString()
                field.setText(value)
            elif type(field) is QCheckBox:
                value = raw_value.toBool()
                field.setChecked(value)
            elif type(field) is QSpinBox:
                value, ok = raw_value.toInt()
                if ok:
                    field.setValue(value)
            elif type(field) is QToolButton:
                value = raw_value.toString()
                setattr(self, '%s_value' % name, QColor(value))

            # keep for compare when saving
            self.defaults[name] = value
        settings.endGroup()

class TabGeneral(UiDlgTemplate, TabAbstract):
    """
    Класс вкладки "Общие настройки".
    """
    ui_file = 'uis/dlg_settings_general.ui'
    groupName = 'general'

    defaults = {
        'borderWidth': 2,
        'borderColor': '#ff0000',
        'debug_app': False,
        'debug_use_ssl': True,
        'debug_reader': False,
        'debug_printer': False,
        }

    def __init__(self, parent):
        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)
        self.connect(self.borderColor, SIGNAL('clicked()'), self.getBorderColor)
        self.borderWidth.setRange(0, 4)

    def getBorderColor(self):

        def callback():
            self.borderColor_value = dialog.selectedColor()

        current_color = self.borderColor_value
        dialog = QColorDialog(current_color, self)
        dialog.open(callback)

class TabNetwork(TabAbstract):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.groupName = 'network'

        self.defaults = {'addressHttpServer': 'localhost',
                         'portHttpServer': '8000',
                         'useProxy': 'false',
                         'addressHttpProxy': '',
                         'portHttpProxy': '',
                         'loginProxyAuth': '',
                         'passwordProxyAuth': ''
                         }

        # the address and port of HTTP server
        labelHttpServer = QLabel(self.tr('HTTP server (address/port)'))
        self.addressHttpServer = QLineEdit()
        self.portHttpServer = QLineEdit()
        boxHttpServer = QHBoxLayout()
        boxHttpServer.addWidget(labelHttpServer)
        boxHttpServer.addWidget(self.addressHttpServer)
        boxHttpServer.addWidget(self.portHttpServer)

        # checkbox to enabling http proxy usage
        self.useProxy = QCheckBox(self.tr('Use HTTP proxy'))

        # http proxy's parameters
        groupHttpProxy = QGroupBox(self.tr('HTTP proxy settings'))

        labelHttpProxy = QLabel(self.tr('Address and port'))
        self.addressHttpProxy = QLineEdit()
        self.portHttpProxy = QLineEdit()
        boxHttpProxy = QHBoxLayout()
        boxHttpProxy.addWidget(self.addressHttpProxy)
        boxHttpProxy.addWidget(self.portHttpProxy)

        labelProxyAuth = QLabel(self.tr('Login and password'))
        self.loginProxyAuth = QLineEdit()
        self.passwordProxyAuth = QLineEdit()
        boxProxyAuth = QHBoxLayout()
        boxProxyAuth.addWidget(self.loginProxyAuth)
        boxProxyAuth.addWidget(self.passwordProxyAuth)

        groupLayout = QGridLayout()
        groupLayout.setColumnStretch(1, 1)
        groupLayout.setColumnMinimumWidth(1, 250)

        groupLayout.addWidget(labelHttpProxy, 0, 0)
        groupLayout.addLayout(boxHttpProxy, 0, 1)
        groupLayout.addWidget(labelProxyAuth, 1, 0)
        groupLayout.addLayout(boxProxyAuth, 1, 1)

        groupHttpProxy.setLayout(groupLayout)

        self.connect(self.useProxy, SIGNAL('toggled(bool)'), groupHttpProxy, SLOT('setDisabled(bool)'))

        # ToDo: implement this, is disabled now
        self.useProxy.setCheckState(Qt.Unchecked)
        groupHttpProxy.setDisabled(True)

        # connect all items together
        mainLayout = QVBoxLayout()
        mainLayout.addStretch(1)
        mainLayout.addLayout(boxHttpServer)
        mainLayout.addWidget(self.useProxy)
        mainLayout.addWidget(groupHttpProxy)
        self.setLayout(mainLayout)

class TabPrinter(UiDlgTemplate):

    ui_file = 'uis/dlg_settings_printer.ui'

    def __init__(self, parent):
        UiDlgTemplate.__init__(self, parent)

    def setupUi(self):
        UiDlgTemplate.setupUi(self)

        self.groupName = 'printer'

        self.defaults = {
            'device_file': '/dev/usblp0',
            }

    def loadSettings(self, settings):
        settings.beginGroup(self.groupName)
        for name in self.defaults.keys():
            field = getattr(self, name)
            raw_value = settings.value(name, QVariant(self.defaults[name]))
            if type(field) is QLineEdit:
                value = raw_value.toString()
                field.setText(value)
            # keep for compare when saving
            self.defaults[name] = value
        settings.endGroup()

    def saveSettings(self, settings):
        is_changed = False
        settings.beginGroup(self.groupName)
        for name in self.defaults.keys():
            field = getattr(self, name)
            if type(field) is QLineEdit:
                value = field.text()
            original_value = self.defaults[name]
            if original_value != value:
                is_changed = True
            settings.setValue(name, QVariant(value))
        settings.endGroup()
        return is_changed

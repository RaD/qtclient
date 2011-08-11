# -*- coding: utf-8 -*-
# (c) 2009-2010 Ruslan Popov <ruslan.popov@gmail.com>

from settings import DEBUG

from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4 import uic

class UiDlgTemplate(QDialog):
    """ This is a common template for all UI dialogs. """

    ui_file = None
    parent = None
    title = None

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        self.parent = parent
        if not self.ui_file:
            raise RuntimeError( self.tr('There is no UI file.') )
        uic.loadUi(self.ui_file, self)
        self.setupUi()

    def setupUi(self):
        if self.title:
            self.setWindowTitle(self.title)

        # каждый UI должен иметь mainLayout!
        self.setLayout(self.mainLayout)

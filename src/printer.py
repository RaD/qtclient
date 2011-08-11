# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from settings import PRINTER_REFRESH_TIMEOUT
from library import ParamStorage

import re

from PyQt4.QtGui import QApplication

class Printer:

    device_file = '/dev/usblp0'
    params = ParamStorage()
    is_ready = False
    refresh_timeout = 1000 # one second
    template = None

    def __init__(self, *args, **kwargs):
        self.error_msg = QApplication.translate('printer', 'No error')
        self.flags = [
            [(QApplication.translate('printer', 'No media'), 1),
             (QApplication.translate('printer', 'Pause is active'), 2),
             (QApplication.translate('printer', 'Buffer is full'), 5),
             (QApplication.translate('printer', 'Diagnostic mode is active'), 6),
             (QApplication.translate('printer', 'Check is printing'), 7),
             (QApplication.translate('printer', 'RAM is corrupted'), 9),
             (QApplication.translate('printer', 'Head is too cold'), 10),
             (QApplication.translate('printer', 'Head is too hot'), 11),
             ],
            [(QApplication.translate('printer', 'Close the lid'), 2),
             (QApplication.translate('printer', 'No ribbon'), 3),
             ],
            ]

        self.device_file = kwargs.get('device_file', '/dev/usblp0')
        self.refresh_timeout = kwargs.get('refresh_timeout', PRINTER_REFRESH_TIMEOUT)
        self.template = kwargs.get('template', '')

        self.DEBUG_PRINTER = 'true' == self.params.app_config(key='General/debug_printer')
        if self.DEBUG_PRINTER:
            print 'PRINTER DEVICE is', self.device_file

        #if not DEBUG_PRINTER:
        #    self.RESET()

    def RESET(self):
        return self.action('~JR', False)
    def HEADI(self):
        return self.action('~HD', True)
    def HOSTI(self):
        return self.action('~HS', True)

    def action(self, mnemonic, do_recv=False, **kwargs):
        ok = self.send(mnemonic, **kwargs)
        if ok and do_recv:
            return self.recv()

    def get_status(self):
        """
        Read the status lines from printer and set READY flag.
        """
        error_list = []

        #import pdb; pdb.set_trace()
        if self.DEBUG_PRINTER:
            out = ['\x02030,0,0,1032,000,0,0,0,000,0,0,0\x03\r\n',
                   '\x02000,0,0,0,0,2,6,0,00000000,1,000\x03\r\n',
                   '\x021234,0\x03\r\n']
        else:
            out = self.HOSTI()

        if not out:
            self.is_ready = False
            return (self.is_ready, self.error_msg)
        else:
            regexp = re.compile(r'\x02([^\x03]+)\x03\r\n')
            for index, flags in enumerate(self.flags):
                body = regexp.match(out[index])
                if body:
                    params = body.group(1).split(',')
                    for error_msg, key in flags:
                        #print key, params[key]
                        if params[key] != '0':
                            error_list.append(error_msg)

            if len(error_list) == 0:
                self.is_ready = True
                return (self.is_ready, QApplication.translate('printer', 'Ready'))
            else:
                self.is_ready = False
                return (self.is_ready, '\n'.join(error_list))

    def send(self, data, *args, **kwargs):
        try:
            p = open(self.device_file, 'w')
            p.write(data)
            p.close()
            return True
        except IOError:
            self.error_msg = QApplication.translate('printer', 'No device')
            return False

    def recv(self):
        try:
            p = open(self.device_file, 'r')
            data = p.readlines()
            p.close()
            return data
        except IOError:
            self.error_msg = QApplication.translate('printer', 'No device')
            return None

    def hardcopy(self, params):
        if self.DEBUG_PRINTER:
            print 'DEBUG_PRINTER'
            import pprint; pprint.pprint(params)
        else:
            output = self.template % params
            self.send(output.encode('utf-8'))

if __name__=="__main__":

    import sys

    p = Printer()
    print p.get_status()
    print p.HOSTI()
    print p.HEADI()
    print p.send("""
^XA^LH190,0^FO0,0
^MNN
^LL320
^CI28,
^CF0,32,96
^FO20,20
^FDZEBRA^FS
^CF0,32,32
^FO20,120
^FDНе выкидывайте меня!^FS
^FO20,180
^FDЯ работоспособен!^FS
^XZ
""")
    sys.exit(0)

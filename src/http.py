# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

import sys, httplib, urllib, json
from datetime import datetime

from dlg_settings import TabNetwork
from library import ParamStorage

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from settings import DEBUG, TEST_CREDENTIALS
DEBUG_COMMON, DEBUG_RFID, DEBUG_PRINTER = DEBUG

class HttpException(Exception):
    pass


class Abstract(object):

    cookie_name = 'advisor_sessionid'
    headers = {
        'Content-type': 'application/x-www-form-urlencoded',
        'Accept': 'text/plain'
        }

    def __init__(self, parent=None):
        self.session_id = None
        self.parent = parent
        self.connect()

    def __del__(self):
        self.disconnect()

    def debug(self, message):
        if DEBUG_COMMON:
            print '%s: %s' % (__name__, message)

    def connect(self):
        (self.host, self.port) = self.get_settings()
        self.hostport = '%s:%s' % (self.host, self.port)
        self.debug('Connect to %s\n%s' % (self.hostport, self.headers))
        self.conn = self.protocol(self.hostport)

    def disconnect(self):
        self.debug('Disconnect')
        self.conn.close()

    def reconnect(self):
        self.disconnect()
        self.connect()

    def is_session_open(self):
        return self.session_id is not None

    def get_settings(self): # private
        """ Use this method to obtain application's network settings. """
        self.settings = QSettings()

        network = TabNetwork()
        network.loadSettings(self.settings)

        host = network.addressHttpServer.text()
        port = network.portHttpServer.text()

        return (host, port)

    def request(self, url, method='POST', params={}, force=False, credentials=None): # public
        self.url = url
        if credentials:
            params = dict(params, **credentials)
        if self.session_id:
            self.headers['Cookie'] = '%s=%s' % (self.cookie_name, self.session_id)
        if force:
            url = urllib.quote(url) + '?' + datetime.now().strftime('%y%m%d%H%M%S')
        if type(params) is dict:
            params = self.prepare(params)
        while True:
            try:
                self.conn.request(method, url, urllib.urlencode(params), self.headers)
                break
            except httplib.CannotSendRequest:
                self.reconnect()
            except Exception, e:
                self.error_msg = '%s%s [%s] %s' % (self.hostport, url, e.errno, e.strerror.decode('utf-8'))
                self.response = None
                return False

        with open('./log.html', 'a') as log:
            log.write(url)

        try:
            self.response = self.conn.getresponse()
        except httplib.BadStatusLine, e:
            print 'BadStatusLine', e

        # sessionid=d5b2996237b9044ba98c5622d6311c43;
        # expires=Tue, 09-Feb-2010 16:32:24 GMT;
        # Max-Age=1209600;
        # Path=/

        cookie_string = self.response.getheader('set-cookie')
        if cookie_string:
            cookie = {}
            for item in cookie_string.split('; '):
                key, value = item.split('=')
                cookie.update( { key: value } )
            if DEBUG_COMMON:
                import pprint
                pprint.pprint(cookie)

            self.session_id = cookie.get(self.cookie_name, None)
            self.debug('session id is %s' % self.session_id)
        return True

    def parse(self, default={}, is_json=True): # public
        if not self.response: # request failed
            return None
        if self.response.status == 200: # http status
            data = self.response.read()

            with open('./log.html', 'a') as log:
                log.write(data)

            if not is_json:
                return data # отдаём как есть

            parser = hasattr(json, 'read') and json.read or json.loads # поддержка 2.5 & 2.6
            try:
                response = parser(data)
            except ValueError:
                return data # не распарсилось, отдаём как есть
            else:
                if 'code' in response and response['code'] != 200:
                    self.error_msg = '[%(code)s] %(desc)s' % response
                    return default
                return response
        elif self.response.status == 302: # authentication
            self.error_msg = self.tr('Authenticate yourself.')
            return default
        elif self.response.status == 500: # error
            self.error_msg = 'Error 500. Check dump!'
            with open('./dump.html', 'w') as dump:
                dump.write(self.response.read())
        else:
            self.error_msg = '[%s] %s' % (self.response.status, self.response.reason)
            return default

    def piston(self):
        status_list = {
            200: 'ALL_OK', 201: 'CREATED', 204: 'DELETED',
            400: 'BAD_REQUEST', 401: 'FORBIDDEN', 404: 'NOT_FOUND', 409: 'DUPLICATE_ENTRY', 410: 'NOT_HERE',
            501: 'NOT_IMPLEMENTED', 503: 'THROTTLED',
            }
        response = self.response.read()
        try:
            index = response.index('|') + 1
            response = response[index:]
        except ValueError:
            pass

        try:
            data = json.loads(response)
        except ValueError:
            data = response
        if self.response.status > 399:
            with open('./dump.html', 'w') as dump:
                dump.write(data)
        status = self.response.status
        print '=-=' * 10
        print self.url
        print data
        if status != 200:
            index = response.find(':') + 1
            data = json.loads(response[index:])
        return (status_list.get(status, 'UNKNOWN'), data)

    def prepare(self, data):
        """
        Метод для предобразования словаря с данными в список
        двухэлементных кортежей. Необходим для передачи M2M данных.

        @type  data: dictionary
        @param data: Словарь с данными.

        @rtype: list of tuples
        @return: Список двухэлементных кортежей с данными.
        """
        out = []
        for key, value in data.items():
            if type(value) is list:
                for item in value:
                    out.append( (key, item) )
            else:
                out.append( (key, value) )
        return out


class Http(Abstract):

    def __init__(self, parent=None):
        self.port = 80
        self.protocol = httplib.HTTPConnection
        super(Http, self).__init__(parent)

class Https(Abstract):

    def __init__(self, parent=None):
        self.port = 443
        self.protocol = httplib.HTTPSConnection
        super(Https, self).__init__(parent)

class WebResource(object):

    params = ParamStorage() # синглтон для хранения данных

    def get(self, parent=None):
        use_ssl_state = unicode(self.params.app_config(key='General/debug_use_ssl')).lower()
        self.use_ssl = u'true' == use_ssl_state
        return self.use_ssl and Https(parent) or Http(parent)

# Test part of module

class TestWindow(QMainWindow):

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.test()

    def test(self):
        # instantiate class object
        http = Http()

        # make anonimous request
        is_success = http.request('/manager/get_rooms/', {})
        if is_success:
            result = http.parse()
            if 'rows' in result:
                print 'anonymous request: test passed'
        else:
            print http.error_msg

        # authenticate test user
        is_success = http.request('/manager/login/', TEST_CREDENTIALS)
        if is_success:
            result = http.parse()
            if 'code' in result and result['code'] == 200:
                print 'authenticate user: test passed'
        else:
            print http.error_msg

        # make autorized request
        from datetime import date
        params = {'to_date': date(2010, 5, 10)}
        is_success = http.request('/manager/fill_week/', params)
        if is_success:
            result = http.parse()
            if 'code' in result and result['code'] == 200:
                print 'authorized request: test passed'
        else:
            print http.error_msg

if __name__=="__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(0)

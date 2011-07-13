# -*- coding: utf-8 -*-
# (c) 2009-2011 Ruslan Popov <ruslan.popov@gmail.com>

from datetime import datetime, date, timedelta
from settings import _, DEBUG, userRoles
from http import HttpException

import json, pprint

def dumpobj(title, value):
    print title
    pprint.pprint(value)

def dictlist2dict(dictlist, key_field):
    """ Данная функция конвертирует список словарей в один словарь,
    используя указанное поле в качестве ключа."""
    def _convertor(listitem):
        if type(listitem) is not dict:
            raise ValueError(_('It expexts a dictionary but took %s') % type(key_field))
        if key_field not in listitem:
            raise KeyError(_('Key "%s" does not exists. Check dictionary.') % key_field)

        result.update( {listitem[key_field]: listitem} )
        return True

    result = {}
    map(_convertor, dictlist)
    return result

def filter_dictlist(dictlist, key_field, value):
    """ This function makes search on the list of dictionaries and
    returns the list of items, which the value of appropriate key
    equals the given value or values."""
    def _search(listitem):
        if type(listitem) is not dict:
            raise ValueError(_('It expexts a dictionary but took %s') % type(key_field))
        if key_field not in listitem:
            raise KeyError(_('Key "%s" does not exists. Check dictionary.') % key_field)
        if type(value) in (list, tuple):
            return listitem[key_field] in value
        else:
            return listitem[key_field] == value

    return filter(_search, dictlist)

def date2str(value):
    valtype = type(value)
    if valtype is date:
        return value.strftime('%Y-%m-%d')
    elif valtype is unicode:
        return value
    else:
        raise RuntimeWarning('It must be date but %s of %s' % (value, type(value)))

def dt2str(value):
    FORMAT = '%Y-%m-%d %H:%M:%S'
    valtype = type(value)
    if valtype is datetime:
        return value.strftime(FORMAT)
    elif valtype is unicode:
        return value
    raise RuntimeWarning('It must be datetime but %s of %s' % (value, type(value)))

class Singleton(type):

    """ Метакласс для реализации классов-одиночек. """

    def __init__(cls, name, bases, dict):
        super(Singleton, cls).__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls,*args,**kw):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kw)
        return cls.instance

import logging

class ParamStorage(object):

    """ Класс-одиночка (синглтон) для хранения текущих параметров
    приложения."""

    __metaclass__ = Singleton

    rooms = {}
    static = None
    http = None

    yesterday = datetime.now() - timedelta(days=1)
    cache_timeout = timedelta(minutes=15)
    cache = {}

    def __init__(self, *args, **kwargs):
        LOG_FILENAME = 'debug.log'
        logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG)

    def debug(self, msg):
        logging.debug(msg)

    def dict_tuple(self, dictionary, key_list):
        """ Метод для конвертации словаря в кортеж по указанному
        списку ключей."""
        out = []
        for i in key_list:
            out.append( dictionary.get(i, None) )
        return tuple(out)

    def dict_crop(self, dictionary, key_list):
        """ Метод для удаления из словаря всех ключей, которые не
        перечислены в списке."""
        for i in dictionary.keys():
            if i not in key_list:
                del(dictionary[i])
        return dictionary

    def dict_norm(self, out_dict, in_dict, key_k, key_v):
        """ Метод для конвертации значений в словаря в словарь key=value. """
        key = in_dict[key_k]
        value = in_dict[key_v]
        return out_dict.update( {key: value} )

    def mapper(self, handler, key_list):
        return lambda x: handler(x, key_list)

    def category_rent_list(self):
        KEY = 'category_rent'
        # получаем время обновления данных
        last_access = self.cache.get('%s_timestamp' % KEY, self.yesterday)
        if datetime.now() - last_access > self.cache_timeout:
            # если время превысило предел, обновляем данные
            try:
                response = self.http.request_full('/manager/get_all/',
                                                  { 'action': 'category_rent', })
            except HttpException, e:
                QMessageBox.critical(self, _('Categories of Rent'),
                                     _('Unable to fetch: %s') % e)
                return []
            else:
                self.cache[KEY] = response['data']
                self.cache['%s_timestamp' % KEY] = datetime.now()
        return self.cache[KEY]

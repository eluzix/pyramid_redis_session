from Cookie import SimpleCookie
import hashlib
import random
import os
from urlparse import urlparse
import time

import msgpack
from pyramid.interfaces import ISession
from pyramid.settings import asbool
from redis.client import StrictRedis
from zope.interface import implements


getpid = hasattr(os, 'getpid') and os.getpid or (lambda: '')


def parse_redis_url(url):
    url = urlparse(url)
    if url.scheme != 'redis':
        raise ValueError('URL scheme does not start with redis://')

    server_port = url.netloc.split(':')
    server = server_port[0]
    if len(server_port) > 1:
        port = int(server_port[1])
    else:
        port = 6379

    db = url.path.replace('/', '')
    if db == '':
        db = 0
    db = int(db)

    return server, port, db


def RedisSessionFactory(**options):
    """ Return a Pyramid session factory using Beaker session settings
    supplied directly as ``**options``"""

    _options = {}
    _options.update(options)
    _redis_servers = []
    for _s in _options.get('url').split(';'):
        _redis_servers.append(parse_redis_url(_s))

    _options['_cookie_name'] = _options.get('key', '_ses_')
    _options['_expire'] = int(_options.get('timeout', 3600))
    _options['_secure'] = asbool(_options.get('secure', True))
    _options['_increase_expire_mod'] = int(_options.get('increase_expire_mod', 10))
    _options['_path'] = _options.get('path', '/')

    class RedisSessionObject():
        implements(ISession)

        def __init__(self, request):
            self._options = _options
            self.rd = None
            self._master_rd = False
            self.request = request
            self._data = None
            self.id = None
            self._new_session = True
            self._changed = False

            cookie = self.request.headers.get('Cookie')
            if cookie is None:
                self.__create_id()
            else:
                c = SimpleCookie()
                c.load(cookie)
                session_cookie = c.get(self._options['_cookie_name'])
                if session_cookie is None:
                    #new session!
                    self.__create_id()
                else:
                    self.id = session_cookie.value
                    self._new_session = False

            def session_callback(request, response):
                exception = getattr(request, 'exception', None)
                commit = self._changed
                increase_expire_mod = _options['_increase_expire_mod']
                if increase_expire_mod > 0:
                    rnd = round(random.random() * 1000000)
                    mod = rnd % increase_expire_mod
                    if not mod:
                    #                        print 'Saving due to increase_expire_mod'
                        commit = True

                if exception is None and commit:
                    self.__save()
                    cookie = SimpleCookie()
                    _cname = self._options['_cookie_name']
                    cookie[_cname] = self.id
                    domain = self._options.get('cookie_domain')
                    cookie[_cname]['path'] = _options['_path']
                    if domain is not None:
                        cookie[_cname]['domain'] = domain
                    if self._options['_secure']:
                        cookie[_cname]['secure'] = True
                    header = cookie[_cname].output(header='')
                    #                    print 'Writing cookie header:',header
                    response.headerlist.append(('Set-Cookie', header))

            request.add_response_callback(session_callback)

        # private methods
        def __init_rd(self, master=False):
            if self.rd is None:
                if master:
                    self.rd = StrictRedis(host=_redis_servers[0][0], port=_redis_servers[0][1], db=_redis_servers[0][2])
                    self._master_rd = True
                else:
                    server = random.choice(_redis_servers)
                    self.rd = StrictRedis(host=server[0], port=server[1], db=server[2])
                    self._master_rd = False
            elif master and not self._master_rd:
                self.rd = StrictRedis(host=_redis_servers[0][0], port=_redis_servers[0][1], db=_redis_servers[0][2])
                self._master_rd = True

        def __key(self):
            return 'rd:ses:%s' % self.id

        def __load(self):
            if self._data is None:
                self.__init_rd()
                data = self.rd.get(self.__key())
                if data is not None:
                    self._data = msgpack.unpackb(data, use_list=True, encoding='utf-8')
                else:
                    self._data = {}

        def __save(self):
            if self._data is not None and len(self._data):
                self.__init_rd(master=True)
                self.rd.setex(self.__key(), self._options['_expire'], msgpack.packb(self._data, encoding='utf-8'))

        def __create_id(self):
            self.id = hashlib.sha1(hashlib.sha1("%f%s%f%s" % (time.time(), id({}), random.random(), getpid())).hexdigest(), ).hexdigest()

        def init_with_id(self, session_id):
            """
            Init the session with custom id. the session data is no loaded immediately but loaded only when data is accessed
            :param session_id:
            :return: self
            """
            self.id = session_id
            self._data = None
            return self

        def set_expire(self, expire):
            self._options['_expire'] = expire

        # ISession API
        def save(self):
            self._changed = True

        def invalidate(self):
            self.__init_rd(master=True)
            self.rd.delete(self.__key())
            #todo: delete cookie

        def changed(self):
            self._changed = True

        def flash(self, msg, queue='', allow_duplicate=True):
            self.__load()
            key = '_flsh:%s_' % queue
            q = self.get(key, [])
            if not allow_duplicate:
                if msg not in q:
                    q.append(msg)
            else:
                q.append(msg)
            self[key] = q

        def pop_flash(self, queue=''):
            self.__load()
            key = '_flsh:%s_' % queue
            q = self.get(key, [])
            if len(q):
                e = q.pop()
                self[key] = q
                return e
            return None

        def peek_flash(self, queue=''):
            self.__load()
            key = '_flsh:%s_' % queue
            q = self.get(key, [])
            if len(q):
                e = q[0]
                return e
            return None

        def new_csrf_token(self):
            token = os.urandom(20).encode('hex')
            self['_csrft_'] = token
            return token

        def get_csrf_token(self):
            token = self.get('_csrft_', None)
            if token is None:
                token = self.new_csrf_token()
            return token

        # mapping methods
        def __getitem__(self, key):
            self.__load()
            return self._data[key]

        def get(self, key, default=None):
            self.__load()
            return self._data.get(key, default)

        def __delitem__(self, key):
            self.__load()
            del self._data[key]
            self._changed = True

        def __setitem__(self, key, value):
            self.__load()
            self._data[key] = value
            self._changed = True

        def keys(self):
            self.__load()
            return self._data.keys()

        def values(self):
            self.__load()
            return self._data.values()

        def items(self):
            self.__load()
            return self._data.items()

        def iterkeys(self):
            self.__load()
            return iter(self._data.keys())

        def itervalues(self):
            self.__load()
            return iter(self._data.values())

        def iteritems(self):
            self.__load()
            return iter(self._data.items())

        def clear(self):
            self.__load()
            self._data = {}
            self._changed = True

        def update(self, d):
            self.__load()
            for k in self._data.keys():
                d[k] = self._data[k]

        def multi_set(self, d):
#            print '[update]', self.id
            self.__load()
            for k in d.keys():
                self._data[k] = d[k]
            self._changed = True

        def setdefault(self, key, default=None):
            """D.setdefault(k[,d]) -> D.get(k,d), also set D[k]=d if k not in D"""
            pass

        def pop(self, k, *args):
            """remove specified key and return the corresponding value
            ``*args`` may contain a single default value, or may not be supplied.
            If key is not found, default is returned if given, otherwise
            ``KeyError`` is raised"""
            pass

        def popitem(self):
            """remove and return some (key, value) pair as a
            2-tuple; but raise ``KeyError`` if mapping is empty"""
            pass

        def __len__(self):
            self.__load()
            return len(self._data)


        def __iter__(self):
            return self.iterkeys()

        def __contains__(self, key):
            self.__load()
            return key in self._data

    #factory end
    return RedisSessionObject


def session_factory_from_settings(settings):
    """ Return a Pyramid session factory using pyramid settings supplied from a Paste configuration file"""
    prefixes = ('session.', 'redis.session.')
    options = {}

    # Pull out any config args meant for redis session. if there are any
    for k, v in settings.items():
        for prefix in prefixes:
            if k.startswith(prefix):
                option_name = k[len(prefix):]
                options[option_name] = v

    return RedisSessionFactory(**options)

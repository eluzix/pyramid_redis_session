pyramid_redis_session
=====================

Provide [redis](http://redis.io/) implementation for pyramid's ISessionFactory and ISession.
Use just like you'll use [pyramid_beaker](https://github.com/Pylons/pyramid_beaker).


How to use
----------
Configure your ini file:

```python
session.type = redis
session.url = redis://redis-master:6379/0
session.key = PRS
session.timeout = 7200
session.secure = yes
session.cookie_domain = pheed.com
session.cookie_expires = true
```

Setup the pyramid's config
--------------------------
When configuring your wsgi app:

```python
import pyramid_redis_session
session_factory = pyramid_redis_session.session_factory_from_settings(settings)
config.set_session_factory(session_factory)
```


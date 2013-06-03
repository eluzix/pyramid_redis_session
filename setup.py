import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()

requires = [
    'pyramid>=1.3.2',
    'Redis>=2.4.0',
    'msgpack-python>=0.3.0',
    ]

test_requires = []

entry_points = ""

setup(name='pyramid_redis_session',
      version=0.4,
      description='provide redis implementation for pyramid\'s ISessionFactory and ISession',
      long_description=README,
      classifiers=[
          "Programming Language :: Python",
          "Framework :: Pyramid",
          "Topic :: Internet :: WWW/HTTP",
          "Topic :: Internet :: WWW/HTTP :: Session",
          ],
      author='Pheed',
      author_email='code@pheed.com',
      url='',
      keywords='web pyramid pylons session redis',
      packages=find_packages(exclude=['tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=test_requires,
      test_suite="",
      entry_points=entry_points,
      paster_plugins=['pyramid'],
      )


import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'pyramid',
    'pyramid_debugtoolbar',
    'pyramid_layout',
    'waitress',
    'slug',
    'substanced',
    'pyramid_tm',
    'velruse',
    'PyBrowserID',
    'redis',
    'sh',
    'beautifulsoup4',
    'pykaraoke',
    ]

setup(name='yss',
      version='0.0',
      description='yss',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web pyramid pylons substanced',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="yss",
      entry_points="""\
      [paste.app_factory]
      main = yss:main
      [console_scripts]
      import_songs = yss.scripts.import_songs:main
      postproc = yss.scripts.postproc:main
      """,
      )


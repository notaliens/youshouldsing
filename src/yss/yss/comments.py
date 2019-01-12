import os

from isso import make_app
from isso import dist
from isso import config as isso_config

from pyramid.wsgi import wsgiapp2

def includeme(config):
    isso_conf = isso_config.load(
        os.path.join(dist.location, dist.project_name, "defaults.ini"),
        config.registry.settings['isso.conffile']
        )
    isso_dbpath = config.registry.settings['isso.dbpath']
    isso_conf.set('general', 'dbpath', isso_dbpath)
    isso = make_app(isso_conf, multiprocessing=False)
    issoview = wsgiapp2(isso)
    config.add_view(issoview, name='isso')

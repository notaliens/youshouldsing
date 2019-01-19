import os

from isso import make_app
from isso import dist
from isso import config as isso_config

from pyramid.wsgi import wsgiapp2
from pyramid.threadlocal import get_current_request

def includeme(config):
    isso_conf = isso_config.load(
        os.path.join(dist.location, dist.project_name, "defaults.ini"),
        config.registry.settings['isso.conffile']
        )
    isso_dbpath = config.registry.settings['isso.dbpath']
    isso_conf.set('general', 'dbpath', isso_dbpath)
    isso = make_app(isso_conf, multiprocessing=False)
    issoapp = isso.app.app.app.app.__closure__[0].cell_contents # XXX
    issoapp.signal.subscriptions['comments.new:before-save'].append(
        assert_current_user)

    issoview = wsgiapp2(isso)
    config.add_view(issoview, name='isso')

def assert_current_user(thread, data):
    request = get_current_request()
    assert request.performer.__name__ == data['author']

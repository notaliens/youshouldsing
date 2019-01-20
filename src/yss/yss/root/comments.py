import logging
import os

from isso import make_app
from isso import dist
from isso import config as isso_config

from pyramid.wsgi import wsgiapp2
from pyramid.threadlocal import get_current_request

from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message
from pyramid.traversal import find_resource
from pyramid.renderers import render

logger = logging.getLogger('yss')

def includeme(config):
    isso_conf = isso_config.load(
        os.path.join(dist.location, dist.project_name, "defaults.ini"),
        config.registry.settings['isso.conffile']
        )
    isso_dbpath = config.registry.settings['isso.dbpath']
    isso_conf.set('general', 'dbpath', isso_dbpath)
    isso = make_app(isso_conf, multiprocessing=False)
    issoapp = isso.app.app.app.app.__closure__[0].cell_contents # XXX lol
    issoapp.signal.subscriptions['comments.new:before-save'].append(
        assert_current_user)
    issoapp.signal.subscriptions['comments.new:finish'].append(
        email_new_comment)

    issoview = wsgiapp2(isso)
    config.add_view(issoview, name='isso')

def assert_current_user(thread, data):
    request = get_current_request()
    assert request.performer.__name__ == data['author']

def email_new_comment(thread, data):
    path = thread['uri']
    request = get_current_request()
    recording = find_resource(request.virtual_root, path)
    performer = recording.performer
    message = Message(
        subject = f'New comment from {request.performer.__name__}',
        recipients = [performer.email],
        body = render('emails/new_comment.pt',
                      dict(recording=recording, request=request))
    )
    mailer = get_mailer(request)
    logger.info(f'sending new comment message via {mailer}')
    mailer.send(message)

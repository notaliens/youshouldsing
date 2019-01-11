import mimetypes
import os
import random

from pyramid.config import Configurator
from substanced import root_factory

from yss.authpolicy import YSSAuthenticationPolicy
from yss.utils import authentication_type

from pyramid_redis_sessions import session_factory_from_settings

random.seed()

def main(global_config, **settings):
    # we dont want these values in our settings.ini
    mail_settings = {
        'mail.host':os.environ.get('YSS_MAIL_HOST', 'localhost'),
        'mail.port':os.environ.get('YSS_MAIL_PORT', '25'),
        'mail.username':os.environ.get('YSS_MAIL_USERNAME', None),
        'mail.password':os.environ.get('YSS_MAIL_PASSWORD', None),
        }
    settings.update(mail_settings)
    settings['redis.sessions.secret'] = os.environ.get(
        'YSS_REDIS_SESSIONS_SECRET', 'seekr1t')
    settings['substanced.secret'] = os.environ.get(
        'YSS_SUBSTANCED_SECRET', 'seekri1')
    mimetypes.add_type('application/font-woff', '.woff')
    secret = settings['substanced.secret']
    authn_policy = YSSAuthenticationPolicy(secret)
    config = Configurator(
        settings=settings,
        root_factory=root_factory,
        authentication_policy=authn_policy,
    )
    session_factory = session_factory_from_settings(settings)
    config.set_session_factory(session_factory)

    config.include('substanced')
    config.include('pyramid_layout')
    config.include('velruse.providers.twitter')
    config.include('velruse.providers.google_oauth2')
    config.include('.root')
    config.include('.evolve')
    config.include('.catalog')
    config.include('.songs')
    config.include('.recordings')
    config.add_twitter_login(
        consumer_key=os.environ['YSS_TWITTER_LOGIN_CONSUMER_KEY'],
        consumer_secret=os.environ['YSS_TWITTER_LOGIN_CONSUMER_SECRET'],
    )
    config.add_google_oauth2_login(
        consumer_key=os.environ['YSS_GOOGLE_LOGIN_CONSUMER_KEY'],
        consumer_secret=os.environ['YSS_GOOGLE_LOGIN_CONSUMER_SECRET'],
        )
    config.add_static_view('static', 'yss.root.views:static')
    config.add_permission('yss.indexed')

    config.add_request_method(
        authentication_type,
        'authentication_type',
        reify=True
    )

    config.scan()
    return config.make_wsgi_app()

from pyramid.config import Configurator

from substanced import root_factory

def main(global_config, **settings):
    config = Configurator(settings=settings, root_factory=root_factory)
    config.include('substanced')
    config.include('pyramid_layout')
    config.include('velruse.providers.twitter')
    config.add_twitter_login_from_settings(prefix='velruse.twitter.')
    config.scan()
    config.add_static_view('static', 'yss:static')
    return config.make_wsgi_app()

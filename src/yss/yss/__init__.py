from pyramid.config import Configurator

from substanced import root_factory

def main(global_config, **settings):
    config = Configurator(settings=settings, root_factory=root_factory)
    config.include('substanced')
    config.scan()
    config.add_static_view('static_yss', 'yss:static')
    return config.make_wsgi_app()

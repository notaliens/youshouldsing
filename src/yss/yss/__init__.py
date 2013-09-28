import json

from pyramid.config import Configurator
from pyramid.config import ConfigurationError
from pyramid.settings import aslist
from substanced import root_factory

from .views import persona_button
from .views import persona_js

def main(global_config, **settings):
    config = Configurator(settings=settings, root_factory=root_factory)
    config.include('substanced')
    config.include('pyramid_layout')
    config.include('velruse.providers.twitter')
    config.add_twitter_login_from_settings(prefix='velruse.twitter.')
    config.add_static_view('static', 'yss:static')
    settings = config.get_settings()

    if 'persona.audiences' not in settings:
        raise ConfigurationError(
            'Missing persona.audiences settings.'
            'See https://developer.mozilla.org/en-US/docs/Persona/'
            'Security_Considerations for details.')
    audiences = aslist(settings['persona.audiences'])

    request_params = {}
    for option in ('privacyPolicy',
                   'siteLogo',
                   'siteName',
                   'termsOfService',
                   'backgroundColor',
                  ):
        setting_name = 'persona.%s' % option
        if setting_name in settings:
            request_params[option] = settings[setting_name]
    config.registry['persona.request_params'] = json.dumps(request_params)

    # Construct a browserid Verifier using the configured audience.
    # This will pre-compile some regexes to reduce per-request overhead.
    verifier = settings.get('persona.verifier', 'browserid.RemoteVerifier')
    verifier_factory = config.maybe_dotted(verifier)
    config.registry['persona.verifier'] = verifier_factory(audiences)

    # Quick access to the login button
    config.add_request_method(persona_button, 'persona_button', reify=True)

    # The javascript needed by persona
    config.add_request_method(persona_js, 'persona_js', reify=True)

    # Route for Persona callback views
    config.add_route('persona', '/persona/*traverse')
    config.scan()
    return config.make_wsgi_app()

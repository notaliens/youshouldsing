import mimetypes
import json

from pyramid.config import Configurator
from pyramid.config import ConfigurationError
from pyramid.settings import aslist
from substanced import root_factory

from .authpolicy import YSSAuthenticationPolicy
from .views.login import authentication_type
from .views.login import persona_js

def main(global_config, **settings):
    mimetypes.add_type('application/font-woff', '.woff')
    secret = settings['substanced.secret']
    authn_policy = YSSAuthenticationPolicy(secret)
    config = Configurator(settings=settings,
                          root_factory=root_factory,
                          authentication_policy=authn_policy,
                         )
    config.include('substanced')
    config.include('pyramid_layout')
    config.include('velruse.providers.twitter')
    config.include('.evolve')
    config.include('.catalog')
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

    # The javascript needed by persona
    config.add_request_method(authentication_type, 'authentication_type',
                              reify=True)
    config.add_request_method(persona_js, 'persona_js', reify=True)

    # Route for Persona callback views
    config.add_route('persona', '/persona/*traverse')
    config.scan()
    return config.make_wsgi_app()

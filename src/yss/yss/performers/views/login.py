import logging

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from pyramid.security import forget
from pyramid.security import remember
from substanced.db import root_factory
from substanced.interfaces import IUserLocator
from substanced.principal import DefaultUserLocator
from substanced.util import (
    find_objectmap,
    get_oid,
    )

from yss.interfaces import PerformerToUser

logger = logging.getLogger('yss')

class LoginViews(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @view_config(
        context='velruse.AuthenticationComplete',
    )
    def velruse_login_complete_view(self):
        context = self.context
        request = self.request
        profile = context.profile
        account = profile['accounts'][0]
        domain = account['domain']
        username = account['username']
        userid = account['userid']
        sd_userid = f'{domain}_{userid}'
        root = root_factory(request)
        adapter = request.registry.queryMultiAdapter(
            (root, request), IUserLocator)
        if adapter is None:
            adapter = DefaultUserLocator(root, request)
        user = adapter.get_user_by_login(sd_userid)
        headers = []
        if user is None:
            photos = profile.get('photos')
            if photos:
                photo_url = photos[0]['value']
                request.session['photo_url'] = photo_url
            request.session['userid'] = sd_userid
            realname = profile['displayName']
            request.session['profilename'] = username
            request.session['realname'] = realname
            location = request.resource_url(root, 'create_profile')
        else:
            objectmap = find_objectmap(root)
            performer = list(objectmap.sources(user, PerformerToUser))[0]
            location = request.resource_url(performer)
            headers = remember(request, get_oid(user))
        return HTTPFound(location, headers=headers)

    @view_config(name='logout')
    def velruse_logout(self):
        request = self.request
        headers = forget(request)
        try:
            del request.user
        except AttributeError:
            pass
        return HTTPFound(location=request.resource_url(request.virtual_root),
                         headers=headers,
                        )


    @view_config(
        context='velruse.AuthenticationDenied',
        renderer='templates/login_denied.pt',
    )
    def velruse_login_denied_view(context, request):
        return {
            'ok': False,
            'provider_name': context.provider_name,
            'reason': context.reason,
        }

def authentication_type(request):
    if request.user is not None:
        if request.user.__name__.startswith('twitter.com_'):
            return 'twitter'
        if request.user.__name__.startswith('accounts.google.com_'):
            return 'google'

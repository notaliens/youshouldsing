import colander
import logging

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from pyramid.security import Allow
from pyramid.security import forget
from pyramid.security import remember
from substanced.db import root_factory
from substanced.interfaces import IUserLocator
from substanced.principal import DefaultUserLocator
from substanced.util import find_service
from substanced.util import get_oid
from substanced.util import set_acl

logger = logging.getLogger('yss')

@view_config(
    context='velruse.AuthenticationComplete',
)
def velruse_login_complete_view(context, request):
    profile = context.profile
    username = profile['accounts'][0]['username']
    root = root_factory(request)
    adapter = request.registry.queryMultiAdapter(
        (root, request), IUserLocator)
    if adapter is None:
        adapter = DefaultUserLocator(root, request)
    user = adapter.get_user_by_login(username)
    if user is None:
        registry = request.registry
        principals = find_service(root, 'principals')
        user = principals.add_user(username, registry=registry)
        performer = registry.content.create('Performer')
        root['performers'][username] = performer
        performer.title = profile['displayName']
        photos = profile.get('photos')
        if photos:
            performer.photo_url = photos[0]['value']
        performer.age = colander.null
        performer.sex = user.favorite_genre = None
        performer.user = user
        set_acl(performer, [(Allow, user.__oid__, ['yss.edit-profile'])])
        location = request.resource_url(performer, 'edit.html')
    else:
        location = request.resource_url(root['performers'][username])
    headers = remember(request, get_oid(user))
    return HTTPFound(location, headers=headers)

@view_config(name='logout')
def velruse_logout(request):
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
        return 'twitter'



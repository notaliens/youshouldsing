import base64
import uuid

import colander
import deform
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from pyramid.security import (
    remember,
    forget,
    )
from substanced.db import root_factory
from substanced.interfaces import IUser
from substanced.interfaces import IUserLocator
from substanced.principal import DefaultUserLocator
from substanced.util import find_service
from substanced.util import get_oid

from .resources import YSSProfileSchema

@view_config(renderer="templates/home.pt")
def home(request):
    return {}

@view_config(name="record",
             renderer="templates/record.pt")
def recording_app(request):
    performance_id = generate_performance_id({})
    return {
        "id": performance_id,
    }


@view_config(name="record", xhr=True)
def save_recording(request):
    pass


def generate_performance_id(performances):
    while True:
        id = base64.b64encode(uuid.uuid4().bytes).rstrip("==")[-8:]
        if id not in performances:
            break
    return id


@view_config(
    context='velruse.AuthenticationComplete',
)
def login_complete_view(context, request):
    provider = context.provider_name
    profile = context.profile
    username = profile['accounts'][0]['username']
    root = root_factory(request)
    adapter = request.registry.queryMultiAdapter(
        (root, request), IUserLocator)
    if adapter is None:
        adapter = DefaultUserLocator(root, request)
    user = adapter.get_user_by_login(username)
    if user is None:
        principals = find_service(root, 'principals')
        user = principals.add_user(username, registry=request.registry)
        user.display_name = profile['displayName']
        addresses = profile.get('addresses')
        if addresses:
            user.email = addresses[0]['formatted']
        photos = profile.get('photos')
        if photos:
            user.photo_url = photos[0]['value']
        user.age = colander.null
        user.sex = user.favorite_genre = None
        location = request.resource_url(user, 'edit.html')
    else:
        location = request.resource_url(user)
    headers = remember(request, get_oid(user))
    return HTTPFound(location, headers=headers)

@view_config(name='logout')
def logout(request):
    headers = forget(request)
    return HTTPFound(location=request.resource_url(request.virtual_root),
                     headers=headers)


@view_config(
    context='velruse.AuthenticationDenied',
    renderer='templates/logged_in.pt',
)
def login_denied_view(context, request):
    return {
        'ok': False,
        'provider_name': context.provider_name,
        'reason': context.reason,
    }


@view_config(
    context=IUser,
    renderer='templates/profile.pt',
)
def profile_view(context, request):
    appstruct = {
        'username': context.__name__,
        'display_name': getattr(context, 'display_name', ''),
        'email': getattr(context, 'email', ''),
        'photo_url': getattr(context, 'photo_url', ''),
        'age': getattr(context, 'age', colander.null),
        'sex': getattr(context, 'sex', None),
        'favorite_genre': getattr(context, 'favorite_genre', None),
    }
    form = deform.Form(YSSProfileSchema(), buttons=('Save',))
    return {
        'form': form.render(appstruct, readonly=True),
    }


@view_config(
    context=IUser,
    renderer='templates/profile.pt',
    name='edit.html',
#    permission='edit', XXX
)
def profile_edit(context, request):
    appstruct = {
        'username': context.__name__,
        'display_name': getattr(context, 'display_name', ''),
        'email': getattr(context, 'email', ''),
        'photo_url': getattr(context, 'photo_url', ''),
        'age': getattr(context, 'age', colander.null),
        'sex': getattr(context, 'sex', None),
        'favorite_genre': getattr(context, 'favorite_genre', None),
    }
    form = deform.Form(YSSProfileSchema(), buttons=('Save',))
    return {
        'form': form.render(appstruct, readonly=False),
    }

import os
import random
import shutil

from browserid.errors import TrustError
import colander
import deform
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.httpexceptions import HTTPFound
from pyramid.session import check_csrf_token
from pyramid.view import view_config
from pyramid.security import (
    authenticated_userid,
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

random.seed()

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


@view_config(name="record", xhr=True, renderer='string')
def save_recording(request):
    f = request.params['data'].file
    id = request.params['id']
    fname = request.params['filename']
    tmpdir = '/tmp/' + id
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    with open('%s/%s' % (tmpdir, fname), 'wb') as output:
        shutil.copyfileobj(f, output)
    return 'OK'


idchars = (
    map(chr, range(ord('a'), ord('z') + 1)) +
    map(chr, range(ord('A'), ord('Z') + 1)) +
    map(chr, range(ord('0'), ord('9') + 1)))


def generate_performance_id(performances):
    while True:
        id = ''.join([random.choice(idchars) for _ in range(8)])
        if id not in performances:
            break
    return id


@view_config(
    context='velruse.AuthenticationComplete',
)
def velruse_login_complete_view(context, request):
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

@view_config(name='logout',
             renderer='templates/persona_logout.pt',
)
def logout(request):
    headers = forget(request)
    try:
        del request.user
    except AttributeError:
        pass
    return {'location': request.resource_url(request.virtual_root)}


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

# Persona integration

_PERSONA_SIGNIN_HTML = (
    '<img src="https://login.persona.org/i/persona_sign_in_blue.png" '
          'id="persona-signin" alt="sign-in button" />')

_PERSONA_SIGNOUT_HTML = '<button id="signout">logout</button>'

PERSONA_JS = """
$(function() {
    $('#persona-signin').click(function() {
        navigator.id.request(%(request_params)s);
        return false;
    });

    $('#signout').click(function() {
        navigator.id.logout();
        return false;
    });

    var currentUser = %(user)s;

    navigator.id.watch({
        loggedInUser: currentUser,
        onlogin: function(assertion) {
            $.ajax({
                type: 'POST',
                url: '%(login)s',
                data: {
                    assertion: assertion,
                    came_from: '%(came_from)s',
                    csrf_token: '%(csrf_token)s'
                },
                dataType: 'json',
                success: function(res, status, xhr) {
                    if(!res['success'])
                        navigator.id.logout();
                    window.location = res['redirect'];
                },
                error: function(xhr, status, err) {
                    navigator.id.logout();
                    alert("Login failure: " + err);
                }
            });
        },
        onlogout: function() {
            $.ajax({
                type: 'POST',
                url: '%(logout)s',
                data:{
                    came_from: '%(came_from)s',
                    csrf_token: '%(csrf_token)s'
                },
                dataType: 'json',
                success: function(res, status, xhr) {
                    window.location = res['redirect'];
                },
                error: function(xhr, status, err) {
                    //alert("Logout failure: " + err);
                }
            });
        }
    });
});
"""

def persona_button(request):
    """Return login button if the user is logged in, else the login button.
    """
    if not authenticated_userid(request):
        return _PERSONA_SIGNIN_HTML
    else:
        return _PERSONA_SIGNOUT_HTML


def persona_js(request):
    """Return the javascript needed to run persona.
    """
    userid = authenticated_userid(request)
    data = {
        'user': "'%s'" % userid if userid else "null",
        'login': '/persona/login',
        'logout': '/persona/logout',
        'csrf_token': request.session.get_csrf_token(),
        'came_from': request.url,
        'request_params': request.registry['persona.request_params'],
    }
    return PERSONA_JS % data

def verify_persona_assertion(request):
    """Verify the assertion and the csrf token in the given request.

    Return the email of the user if everything is valid.

    otherwise raise HTTPBadRequest.
    """
    verifier = request.registry['persona.verifier']
    try:
        data = verifier.verify(request.POST['assertion'])
    except (ValueError, TrustError) as e:
        raise HTTPBadRequest('Invalid assertion')
    return data['email']

@view_config(
    name='login',
    route_name='persona',
    renderer='json',
    )
def persona_login(context, request):
    check_csrf_token(request)
    email = verify_persona_assertion(request)
    root = root_factory(request)
    adapter = request.registry.queryMultiAdapter(
        (root, request), IUserLocator)
    if adapter is None:
        adapter = DefaultUserLocator(root, request)
    user = adapter.get_user_by_email(email)
    if user is None:
        username = 'persona:%s' % email
        principals = find_service(root, 'principals')
        user = principals.add_user(username, registry=request.registry)
        user.display_name = email
        user.email = email
        user.photo_url = None
        user.age = colander.null
        user.sex = user.favorite_genre = None
        location = request.resource_url(user, 'edit.html')
    else:
        location = request.resource_url(user)
    headers = remember(request, get_oid(user))
    request.response.headers.extend(headers)
    return {'redirect': location, 'success': True}


@view_config(
    name='logout',
    route_name='persona',
    renderer='json',
    )
def persona_logout(context, request):
    """View to forget the user
    """
    request.response.headers.extend(forget(request))
    return {'redirect': request.POST['came_from']}

# Retail profile views

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

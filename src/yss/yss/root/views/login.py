import logging

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from pyramid.security import forget
from pyramid.security import remember
from pyramid.session import check_csrf_token
from substanced.db import root_factory
from substanced.event import LoggedIn
from substanced.interfaces import IUserLocator
from substanced.principal import DefaultUserLocator
from substanced.util import (
    find_objectmap,
    get_oid,
    )

from yss.interfaces import PerformerToUser

logger = logging.getLogger('yss')

class VelruseLoginViews(object):
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

@view_config(
    content_type='Root',
    name='internal_login',
    renderer='templates/internal_login.pt'
    )
def internal_login(context, request):

    login = ''
    password = ''

    if 'form.submitted' in request.POST:
        try:
            check_csrf_token(request)
        except:
            request.sdiapi.flash('Failed login (CSRF)', 'danger')
        else:
            login = request.POST['login']
            password = request.POST['password']
            root = request.root
            adapter = request.registry.queryMultiAdapter(
                (root, request), IUserLocator)
            if adapter is None:
                adapter = DefaultUserLocator(root, request)
            user = adapter.get_user_by_login(login)
            if user is None:
                request.session.flash('Bad username or password', 'danger')
            else:
                if user.check_password(password):
                    request.registry.notify(LoggedIn(
                        login, user, context, request))
                    objectmap = find_objectmap(root)
                    try:
                        performer = list(
                            objectmap.sources(user, PerformerToUser)
                        )[0]
                    except IndexError:
                        request.session.flash(
                            'No performer associated with account', 'danger'
                        )
                    else:
                        headers = remember(request, get_oid(user))
                        location = request.resource_url(performer)
                        return HTTPFound(location, headers=headers)
                else:
                    request.session.flash('Bad username or password', 'danger')

    return {
        'login':login,
        'password':password,
        'login_url':request.resource_url(
            request.virtual_root, '@@internal_login'),
    }

@view_config(name='logout')
def logout(context, request):
    headers = forget(request)
    try:
        del request.user
    except AttributeError:
        pass
    return HTTPFound(
        location=request.resource_url(request.virtual_root),
        headers=headers
    )

import colander
import deform
import deform.widget

from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound

from substanced.interfaces import IPasswordReset
from substanced.schema import Schema
from substanced.util import find_service

@colander.deferred
def login_validator(node, kw):
    context = kw['context']
    def _login_validator(node, value):
        principals = find_service(context, 'principals')
        users = principals['users']
        user = users.get('value')
        if user is None:
            raise colander.Invalid(node, 'No such user %s' % value)
        if not user.email:
            raise colander.Invalid(
                node,
                'Cannot send reset request, user does not have a valid email')
    return _login_validator

class ResetRequestSchema(Schema):
    """ The schema for validating password reset requests."""
    login = colander.SchemaNode(
        colander.String(),
        validator = login_validator,
        )

@view_config(
    name='resetpassword',
    renderer='templates/form.pt',
    permission=NO_PERMISSION_REQUIRED,
    )
def password_reset_request(context, request):
    schema = ResetRequestSchema()
    schema = ResetRequestSchema().bind(request=request, context=context)
    form = deform.Form(schema, buttons=('Send',))
    rendered = None
    if 'Reset' in request.POST:
        controls = request.POST.items()
        try:
            appstruct = form.validate(controls)
        except deform.ValidationFailure as e:
            rendered = e.render()
        else:
            login = appstruct['login']
            principals = find_service(context, 'principals')
            users = principals['users']
            user = users[login]
            user.email_password_reset(request)
            request.sdiapi.flash('Emailed you password reset instructions',
                                 'success')
            home = request.resource_url(request.virtual_root)
            return HTTPFound(location=home)
    else:
        appstruct = {
            'csrf_token': request.session.get_csrf_token(),
            'login': colander.null,
        }
    if rendered is None:
        rendered = form.render(appstruct, readonly=False)
    return {
        'form':rendered,
        }

class ResetSchema(Schema):
    """ The schema for validating password reset requests."""
    new_password = colander.SchemaNode(
        colander.String(),
        validator = colander.Length(min=3, max=100),
        widget = deform.widget.CheckedPasswordWidget(),
        )

@view_config(
    context=IPasswordReset,
    name='',
    renderer='templates/form.pt',
    permission=NO_PERMISSION_REQUIRED,
    )
def password_reset(context, request):
    schema = ResetSchema().bind(request=request, context=context)
    form = deform.Form(schema, buttons=('Reset',))
    rendered = None
    if 'Reset' in request.POST:
        controls = request.POST.items()
        try:
            appstruct = form.validate(controls)
        except deform.ValidationFailure as e:
            rendered = e.render()
        else:
            context.reset_password(appstruct['new_password'])
            request.session.flash(
                'Password reset, you may now log in', 'success')
            home = request.resource_url(request.virtual_root)
            return HTTPFound(location=home)
    else:
        appstruct = {
            'csrf_token': request.session.get_csrf_token(),
            'new_password': colander.null,
        }
    if rendered is None:
        rendered = form.render(appstruct, readonly=False)
    return {
        'form':rendered,
        }

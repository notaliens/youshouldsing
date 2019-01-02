import colander
import deform
import pytz

from pyramid.security import remember
from pyramid.traversal import find_root

from substanced.schema import Schema

from pyramid.view import view_config
from substanced.util import find_service, set_acl, get_oid

from pyramid.security import Allow
from pyramid.httpexceptions import HTTPFound

from yss.interfaces import (
    sex_choices,
    genre_choices,
)

_ZONES = pytz.all_timezones

@colander.deferred
def tzname_widget(node, kw): #pragma NO COVER
    return deform.widget.Select2Widget(values=zip(_ZONES, _ZONES))

@colander.deferred
def profilename_validator(node, kw):
    context = kw['context']
    def _profilename_validator(node, value):
        root = find_root(context)
        performers = root['performers']
        if value in performers:
            raise colander.Invalid(node, 'Username already taken %s' % value)
    return _profilename_validator

class CreatePerformerSchema(Schema):
    """ Property schema to create a Performer.
    """
    username = colander.SchemaNode(
        colander.String(),
        title='Username',
        validator=profilename_validator,
        )
    title = colander.SchemaNode(
        colander.String(),
        title='Real Name',
        missing='',
    )
    email = colander.SchemaNode(
        colander.String(),
        validator=colander.All(
            colander.Email(),
            colander.Length(max=100)
            ),
        )
    tzname = colander.SchemaNode(
        colander.String(),
        title='Timezone',
        widget=tzname_widget,
        validator=colander.OneOf(_ZONES),
        default='UTC',
        )
    photo_url = colander.SchemaNode(
        colander.String(),
        title='Photo URL',
        missing='',
        validator=colander.url,
        )
    age = colander.SchemaNode(
        colander.Int(),
        title='Age',
        validator=colander.Range(min=0, max=150),
        )
    sex = colander.SchemaNode(
        colander.String(),
        title='Gender',
        widget=deform.widget.SelectWidget(values=sex_choices),
    )
    genre = colander.SchemaNode(
        colander.String(),
        title='Favorite Genre',
        widget=deform.widget.SelectWidget(values=genre_choices),
    )

@view_config(
    name='create_profile',
    permission='view',
    renderer='templates/profile_create.pt',
)
def create_profile(context, request):
    schema = CreatePerformerSchema().bind(request=request, context=context)
    form = deform.Form(schema, buttons=('Save',))
    rendered = None
    if 'Save' in request.POST:
        controls = request.POST.items()
        try:
            appstruct = form.validate(controls)
        except deform.ValidationFailure as e:
            rendered = e.render()
        else:
            registry = request.registry
            principals = find_service(context, 'principals')
            root = find_root(context)
            username = appstruct['username']
            user = principals.add_user(username, registry=registry)
            performer = registry.content.create('Performer')
            root['performers'][username] = performer
            # NB: performer.user required before setting tzname and email
            performer.user = user
            performer.title = appstruct['title']
            performer.email = appstruct['email']
            performer.age = appstruct['age']
            performer.sex = appstruct['sex']
            performer.genre = appstruct['genre']
            performer.tzname = appstruct['tzname']
            performer.photo_url = appstruct['photo_url']
            set_acl(performer, [(Allow, user.__oid__, ['yss.edit'])])
            headers = remember(request, get_oid(user))
            return HTTPFound(request.resource_url(performer), headers=headers)
    else:
        appstruct = {
            'csrf_token': request.session.get_csrf_token(),
            'username': request.session.get('profilename'),
            'title': request.session.get('realname', ''),
            'email': '',
            'photo_url': request.session.get('photo_url', ''),
            'age': colander.null,
            'sex': colander.null,
            'genre': colander.null,
            'tzname': colander.null,
        }
    if rendered is None:
        rendered = form.render(appstruct, readonly=False)
    return {
        'form':rendered,
        }

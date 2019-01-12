import colander
import datetime
import deform
import io
import PIL.Image
import pytz

from pyramid.security import remember
from pyramid.traversal import find_root

from substanced.schema import Schema

from pyramid.view import view_config
from substanced.util import find_service, set_acl, get_oid, find_index
from substanced.file import FileNode

from pyramid.security import Allow
from pyramid.httpexceptions import HTTPFound

from yss.interfaces import (
    sex_choices,
    genre_choices,
    IPerformerPhoto,
)
from yss.performers import photo_validator

from zope.interface import alsoProvides

_ZONES = pytz.all_timezones

@colander.deferred
def tzname_widget(node, kw): #pragma NO COVER
    return deform.widget.Select2Widget(values=zip(_ZONES, _ZONES))

@colander.deferred
def profilename_validator(node, kw):
    context = kw['context']
    def _profilename_validator(node, value):
        if len(value) > 15:
            raise colander.Invalid(
                node, 'Username must not exceed 15 characters')
        root = find_root(context)
        performers = root['performers']
        if value in performers:
            raise colander.Invalid(node, 'Username already taken %s' % value)
    return _profilename_validator

@colander.deferred
def invite_code_validator(node, kw):
    context = kw['context']
    def _invite_code_validator(node, value):
        if not value:
            raise colander.Invalid(node, f'Invitation code required')
        value = value.upper()
        ctindex = find_index(context, 'system', 'content_type')
        nameindex = find_index(context, 'system', 'name')
        q = ctindex.eq('Invitation') & nameindex.eq(value)
        results = list(q.execute())
        if not results:
            raise colander.Invalid(node, f'No such invite code {value}')
        if results[0].redeemer:
            raise colander.Invalid(
                node, f'Sorry, invite code {value} was already redeemed')
    return _invite_code_validator

class CreatePerformerSchema(Schema):
    """ Property schema to create a Performer.
    """
    username = colander.SchemaNode(
        colander.String(),
        title='Profile Name',
        validator=profilename_validator,
        )
    title = colander.SchemaNode(
        colander.String(),
        title='Real Name',
        validator=colander.Length(max=60),
        missing='',
    )
    email = colander.SchemaNode(
        colander.String(),
        validator=colander.All(
            colander.Email(),
            colander.Length(max=100)
            ),
        )
    location = colander.SchemaNode(
        colander.String(),
        validator=colander.Length(max=100),
        missing='',
        )

    tzname = colander.SchemaNode(
        colander.String(),
        title='Timezone',
        widget=tzname_widget,
        validator=colander.OneOf(_ZONES),
        default='UTC',
        )
    photo = FileNode(
        title='Photo',
        validator=photo_validator,
    )
    birthdate = colander.SchemaNode(
        colander.Date(),
        title='Birth Date',
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
    invite_code = colander.SchemaNode(
        colander.String(),
        title='Invite Code',
        validator=invite_code_validator,
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
            userid = request.session['userid']
            user = principals.add_user(userid, registry=registry)
            performer = registry.content.create('Performer')
            root['performers'][username] = performer
            performer['recordings'] = registry.content.create('Recordings')
            performer['invitations'] = registry.content.create('Invitations')
            performer['invitations'].add_more(10)
            phdata = appstruct['photo']
            fp = phdata.get('fp')
            if fp is not None:
                for photoname, photosize in (
                        ('photo', (320, 320)),
                        ('photo_thumbnail', (40, 40)),
                ):
                    photo = registry.content.create('File')
                    alsoProvides(photo, IPerformerPhoto) # for view lookup
                    performer[photoname] = photo
                    fp.seek(0)
                    pil_image = PIL.Image.open(fp)
                    if pil_image.size[0] != photosize[0]: # width
                        pil_image.thumbnail(photosize, PIL.Image.ANTIALIAS)
                    buffer = io.BytesIO()
                    pil_image.save(buffer, 'png')
                    buffer.seek(0)
                    photo.upload(buffer)
                    photo.mimetype = 'image/png'
            # NB: performer.user required before setting tzname and email
            performer.user = user
            performer.title = appstruct['title']
            performer.email = appstruct['email']
            performer.birthdate = appstruct['birthdate']
            performer.sex = appstruct['sex']
            performer.genre = appstruct['genre']
            performer.tzname = appstruct['tzname']
            performer.location = appstruct['location']
            ctindex = find_index(context, 'system', 'content_type')
            nameindex = find_index(context, 'system', 'name')
            q = ctindex.eq('Invitation') & nameindex.eq(
                appstruct['invite_code'].upper())
            results = list(q.execute())
            if results:
                invitation = results[0]
                invitation.redeemer = performer
                invitation.redemption_date = datetime.datetime.utcnow(
                ).replace(tzinfo=pytz.UTC)
            set_acl(performer, [(Allow, user.__oid__, ['yss.edit'])])
            headers = remember(request, get_oid(user))
            return HTTPFound(request.resource_url(performer), headers=headers)
    else:
        appstruct = {
            'csrf_token': request.session.get_csrf_token(),
            'username': request.session.get('profilename'),
            'title': request.session.get('realname', ''),
            'email': '',
            'photo':colander.null,
            'birthdate': colander.null,
            'sex': colander.null,
            'genre': colander.null,
            'tzname': colander.null,
            'location':colander.null,
        }
    if rendered is None:
        rendered = form.render(appstruct, readonly=False)
    return {
        'form':rendered,
        }
create_profile.page_title = 'Create Profile'

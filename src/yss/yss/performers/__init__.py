import colander
import datetime
import deform
import io
import PIL.Image
import pytz

from substanced.content import content
from substanced.event import (
    subscribe_will_be_removed,
    subscribe_removed,
    )
from substanced.file import FileNode
from substanced.folder import Folder
from substanced.objectmap import (
    multireference_source_property,
    multireference_target_property,
    multireference_targetid_property,
    reference_source_property,
    reference_target_property,
    )
from substanced.principal import (
    User as BaseUser,
    UserPropertySheet,
    UserGroupsPropertySheet,
    )

from substanced.property import PropertySheet
from substanced.schema import Schema
from substanced.util import (
    renamer,
    find_service,
    )

from zope.interface import implementer

from yss.interfaces import (
    IPerformer,
    IPerformers,
    PerformerToUser,
    PerformerLikesPerformer,
    PerformerLikesRecording,
    PerformerLikesSong,
    RecordingToPerformer,
    RelatedPropertySheet,
    sex_choices,
    genre_choices,
)

_ZONES = pytz.all_timezones

@content(
    'User',
    icon='glyphicon glyphicon-user',
    add_view='add_user',
    tab_order=('properties',),
    propertysheets = (
        ('Preferences', UserPropertySheet),
        ('Groups', UserGroupsPropertySheet),
        )
    )
class User(BaseUser):
    performer = reference_target_property(PerformerToUser)

@colander.deferred
def tzname_widget(node, kw): #pragma NO COVER
    return deform.widget.Select2Widget(values=zip(_ZONES, _ZONES))

@colander.deferred
def photo_validator(node, kw):
    def _photo_validator(node, value):
        if not value['mimetype'].startswith('image/'):
            raise colander.Invalid(node, 'Photo must be an image')
        value['fp'].seek(0)
        try:
            pil_image = PIL.Image.open(value['fp'])
            pil_image.thumbnail((640, 640), PIL.Image.ANTIALIAS)
            buffer = io.BytesIO()
            pil_image.save(buffer, 'png')
            value['fp'] = buffer
        except OSError:
            raise colander.Invalid(node, 'Photo must be an image')
    return _photo_validator

class PerformerProfileSchema(Schema):
    """ Property schema for Performer.
    """
    title = colander.SchemaNode(
        colander.String(),
        title='Real Name',
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
        validator=colander.OneOf(_ZONES)
        )
    photo = FileNode(
        title='Photo',
        validator=photo_validator,
    )
    birthdate = colander.SchemaNode(
        colander.Date(),
        title='Birth Date',
        missing=colander.null,
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

class PerformerProfilePropertySheet(PropertySheet):
    schema = PerformerProfileSchema()

@content(
    'Performers',
    icon='glyphicon glyphicon-bullhorn',
    )
@implementer(IPerformers)
class Performers(Folder):
    pass

@content(
    'Performer',
    icon='glyphicon glyphicon-user',
    add_view='add_performer',
    tab_order=('properties',),
    propertysheets = (
        ('Profile', PerformerProfilePropertySheet),
        ('Related', RelatedPropertySheet),
        )
    )
@implementer(IPerformer)
class Performer(Folder):
    name = renamer()
    user = reference_source_property(PerformerToUser)
    birthdate = None # bw compat
    location = ''
    recordings = multireference_target_property(RecordingToPerformer)
    liked_by = multireference_target_property(PerformerLikesPerformer)
    liked_by_ids = multireference_targetid_property(PerformerLikesPerformer)
    likes_performers = multireference_source_property(PerformerLikesPerformer)
    likes_songs = multireference_source_property(PerformerLikesSong)
    likes_recordings = multireference_source_property(PerformerLikesRecording)
    divulge_age = True
    divulge_realname = False
    divulge_sex = True
    divulge_location = True
    divulge_song_likes = True
    divulge_performer_likes = True
    divulge_recording_likes = True
    divulge_genre = True

    @property
    def num_likes(self):
        return len(self.liked_by_ids)

    # proxy timezone and email settings to related User object

    def _tzname_set(self, name):
        self.user.tzname = name

    def _tzname_get(self):
        return self.user.tzname

    tzname = property(_tzname_get, _tzname_set)

    def _email_set(self, email):
        self.user.email = email

    def _email_get(self):
        return self.user.email

    email = property(_email_get, _email_set)

    @property
    def age(self):
        birthdate = self.birthdate
        if birthdate is None:
            return 0
        today = datetime.date.today()
        return (today.year - birthdate.year -
                ((today.month, today.day) < (birthdate.month, birthdate.day)))


@subscribe_will_be_removed(content_type='Performer')
def performer_will_be_removed(event):
    # delete recordings made by the performer when we delete a performer.
    # see performer_removed for further stupid, where we delete the
    # principal associated with the performer.

    if event.moving is not None: # it's not really being removed
        return

    performer = event.object

    for recording in performer.recordings:
        recording.__parent__.remove(recording.__name__)


@subscribe_removed(content_type='Performer')
def performer_removed(event):
    # delete principal associated with performer. we can't do this in
    # performer_will_be_removed because of the PrincipalToACLBearing
    # relationship source_integrity (the principal hasn't yet been deleted, so
    # we can't delete the user).  XXX Note that this is insanity, we need
    # cascading deletes in substanced instead of this ghetto version where we
    # split these associated ops across events.

    if event.moving is not None:
        return

    principals = find_service(event.parent, 'principals')
    users = principals['users']
    if event.name in users:
        users.remove(event.name)

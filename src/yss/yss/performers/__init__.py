import colander
import deform
import pytz

from substanced.content import content
from substanced.folder import Folder
from substanced.objectmap import multireference_source_property
from substanced.objectmap import multireference_target_property
from substanced.objectmap import multireference_targetid_property
from substanced.objectmap import reference_source_property
from substanced.objectmap import reference_target_property
from substanced.principal import User as BaseUser
from substanced.principal import UserPropertySheet
from substanced.principal import UserGroupsPropertySheet
from substanced.property import PropertySheet
from substanced.schema import Schema
from substanced.util import renamer

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

class PerformerProfileSchema(Schema):
    """ Property schema for Performer.
    """
    title = colander.SchemaNode(
        colander.String(),
        title='Display Name',
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
        validator=colander.OneOf(_ZONES)
        )
    photo_url = colander.SchemaNode(
        colander.String(),
        title='Photo URL',
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
    recordings = multireference_target_property(RecordingToPerformer)
    liked_by = multireference_target_property(PerformerLikesPerformer)
    liked_by_ids = multireference_targetid_property(PerformerLikesPerformer)
    likes_performers = multireference_source_property(PerformerLikesPerformer)
    likes_songs = multireference_source_property(PerformerLikesSong)
    likes_recordings = multireference_source_property(PerformerLikesRecording)

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

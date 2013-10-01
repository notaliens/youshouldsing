import audioread
import colander
import deform
import persistent

from substanced.content import content
from substanced.file import (
    File,
    FilePropertiesSchema,
    FileUploadPropertySheet,
    )
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
from substanced.schema import MultireferenceIdSchemaNode
from substanced.schema import Schema
from substanced.util import get_oid
from substanced.util import renamer
from zope.interface import implementer

from .interfaces import (
    IPerformer,
    IPerformers,
    IRecording,
    IRecordings,
    ISong,
    ISongs,
    PerformerLikesPerformer,
    PerformerLikesRecording,
    PerformerLikesSong,
    PerformerToUser,
    RecordingToPerformer,
    RecordingToSong,
    )


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

_sex_choices = (('', '- Select -'),
                ('Female', 'Female'),
                ('Male', 'Male')
               )

_genre_choices = (('', '- Select -'),
                  ('Unknown', 'Unknown'),
                  ('Rock', 'Rock'),
                  ('Pop', 'Pop'),
                  ('Country', 'Country'),
                  ('Jazz', 'Jazz'),
                  ('Blues', 'Blues'),
                 )

def performers_choices(context, request):
    performers = request.virtual_root.get('performers')
    if performers is None:
        return () # fbo dump/load
    values = [(get_oid(performer), name) for name, performer in 
                performers.items()]
    return values

class RelatedSchema(Schema):
    liked_by_ids = MultireferenceIdSchemaNode(
        choices_getter=performers_choices,
        title='Liked By',
        )

class RelatedPropertySheet(PropertySheet):
    schema = RelatedSchema()

class PerformerProfileSchema(Schema):
    """ Property schema for :class:`substanced.principal.User` objects.
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
        title='Sex',
        widget=deform.widget.SelectWidget(values=_sex_choices),
    )
    genre = colander.SchemaNode(
        colander.String(),
        title='Favorite Genre',
        widget=deform.widget.SelectWidget(values=_genre_choices),
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
    def likes(self):
        return len(self.liked_by)

class SongSchema(FilePropertiesSchema):
    artist = colander.SchemaNode(colander.String())
    genre = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.SelectWidget(values=_genre_choices),
    )
    duration = colander.SchemaNode(
        colander.Int(),
        missing=colander.null,
        title='Duration in seconds',
        widget = deform.widget.TextInputWidget(readonly=True),
        )
    timings = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.TextAreaWidget(style="height: 200px;"),
        )

class SongPropertySheet(PropertySheet):
    schema = SongSchema()
    def set(self, appstruct):
        return PropertySheet.set(self, appstruct, omit=('duration'))

@content(
    'Songs',
    icon='glyphicon glyphicon-music',
    )
@implementer(ISongs)
class Songs(Folder):
    pass


@content(
    'Song',
    icon='glyphicon glyphicon-music',
    propertysheets=(
        ('Basic', SongPropertySheet),
        ('Related', RelatedPropertySheet),
        ('Upload', FileUploadPropertySheet),
    ),
    add_view='add_song'
    )
@implementer(ISong)
class Song(File):

    genre = 'Unknown'
    recordings = multireference_target_property(RecordingToSong)
    liked_by = multireference_target_property(PerformerLikesSong)
    liked_by_ids = multireference_targetid_property(PerformerLikesSong)
    duration = 0

    def __init__(self, title, artist, timings, audio_stream,
                 audio_mimetype='audio/mpeg'):
        File.__init__(self, audio_stream, audio_mimetype, title)
        self.artist = artist
        self.timings = timings

    @property
    def likes(self):
        return len(self.liked_by)

    def upload(self, stream, mimetype_hint=None):
        result = File.upload(self, stream, mimetype_hint)
        duration = audioread.audio_open(self.blob._p_blob_uncommitted).duration
        self.duration = duration
        return result

    def duration_str(self):
        minutes = int(self.duration) // 60
        seconds = int(self.duration) % 60
        return '%s:%02d' % (minutes, seconds)

@content(
    'Recordings',
    icon='glyphicon glyphicon-record',
    )
@implementer(IRecordings)
class Recordings(Folder):
    pass


@content(
    'Recording',
    icon='glyphicon glyphicon-record',
    propertysheets=(
    #   ('Basic', RecordingPropertySheet),
        ('Related', RelatedPropertySheet),
    ),
    add_view='add_recording'
)
@implementer(IRecording)
class Recording(persistent.Persistent):
    performer = reference_source_property(RecordingToPerformer)
    song = reference_source_property(RecordingToSong)
    liked_by = multireference_target_property(PerformerLikesRecording)
    liked_by_ids = multireference_targetid_property(PerformerLikesRecording)

    @property
    def title(self):
        return getattr(self.song, 'title', 'Unknown')

    @property
    def genre(self):
        return getattr(self.song, 'genre', 'Unknown')

    @property
    def likes(self):
        return len(self.liked_by)

    def __init__(self, tmpfolder):
        self.blob = None
        self.tmpfolder = tmpfolder

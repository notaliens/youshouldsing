import audioread
import colander
import deform

from substanced.content import content
from substanced.file import File
from substanced.file import FilePropertiesSchema
from substanced.file import FileUploadPropertySheet
from substanced.folder import Folder
from substanced.objectmap import multireference_target_property
from substanced.objectmap import multireference_targetid_property
from substanced.property import PropertySheet
from substanced.schema import NameSchemaNode
from substanced.util import renamer
from zope.interface import implementer

from yss.interfaces import (
    ISong,
    ISongs,
    PerformerLikesSong,
    RecordingToSong,
    RelatedPropertySheet,
    genre_choices,
    )

class SongSchema(FilePropertiesSchema):
    name = NameSchemaNode(
        editing=lambda c, r: r.registry.content.istype(c, 'Song'),
        )
    artist = colander.SchemaNode(colander.String())
    genre = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.SelectWidget(values=genre_choices),
    )
    duration = colander.SchemaNode(
        colander.Int(),
        missing=colander.null,
        title='Duration in seconds',
        widget = deform.widget.TextInputWidget(readonly=True),
        )
    lyrics = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.TextAreaWidget(style="height: 200px;"),
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

    name = renamer()
    genre = 'Unknown'
    recordings = multireference_target_property(RecordingToSong)
    liked_by = multireference_target_property(PerformerLikesSong)
    liked_by_ids = multireference_targetid_property(PerformerLikesSong)
    duration = 0

    def __init__(self, title, artist, lyrics, timings, audio_stream,
                 audio_mimetype='audio/mpeg'):
        File.__init__(self, audio_stream, audio_mimetype, title)
        self.artist = artist
        self.lyrics = lyrics
        self.timings = timings

    @property
    def num_likes(self):
        return len(self.liked_by_ids)

    @property
    def num_recordings(self):
        return len(self.recordings)

    def upload(self, stream, mimetype_hint=None):
        result = File.upload(self, stream, mimetype_hint)
        duration = audioread.audio_open(self.blob._p_blob_uncommitted).duration
        self.duration = duration
        return result

    def duration_str(self):
        minutes = int(self.duration) // 60
        seconds = int(self.duration) % 60
        return '%s:%02d' % (minutes, seconds)

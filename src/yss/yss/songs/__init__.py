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
from substanced.objectmap import reference_target_property
from substanced.property import PropertySheet
from substanced.schema import NameSchemaNode
from substanced.util import renamer
from zope.interface import implementer

from yss.interfaces import (
    ISong,
    ISongs,
    PerformerLikesSong,
    PerformerUploadedSong,
    RecordingToSong,
    RelatedPropertySheet,
    genre_choices,
    language_choices,
    )

class SongSchema(FilePropertiesSchema):
    name = NameSchemaNode(
        editing=lambda c, r: r.registry.content.istype(c, 'Song'),
        )
    artist = colander.SchemaNode(colander.String())
    genre = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.Select2Widget(values=genre_choices),
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
    alt_timings = colander.SchemaNode(
        colander.String(),
        missing='',
        widget=deform.widget.TextAreaWidget(style="height: 200px;"),
        )
    language = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.Select2Widget(values=language_choices),
    )
    year = colander.SchemaNode(
        colander.Int(),
        validator=colander.Range(0, 3000),
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
    recording_ids = multireference_targetid_property(RecordingToSong)
    liked_by = multireference_target_property(PerformerLikesSong)
    liked_by_ids = multireference_targetid_property(PerformerLikesSong)
    uploader = reference_target_property(PerformerUploadedSong)
    duration = 0
    language = 'en-US'
    alt_timings = ''
    retiming_blob = None
    retiming = False
    year = colander.null

    def __init__(self, title, artist, lyrics, timings, audio_stream,
                 audio_mimetype='audio/mpeg', language='en-US'):
        File.__init__(self, audio_stream, audio_mimetype, title)
        self.artist = artist
        self.lyrics = lyrics
        self.timings = timings
        self.language = language

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

def includeme(config):
    config.add_static_view('songstatic', 'yss.songs:static')

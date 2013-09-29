import colander
import deform
import persistent
import shutil

from substanced.content import content
from substanced.folder import Folder
from substanced.objectmap import reference_sourceid_property
from substanced.objectmap import reference_source_property
from substanced.property import PropertySheet
from substanced.schema import Schema
from substanced.util import renamer
from ZODB.blob import Blob
from zope.interface import implementer

from .interfaces import (
    CreatorToSong,
    IPerformer,
    IPerformers,
    IRecording,
    IRecordings,
    ISong,
    ISongs,
    PerformerToUser,
    RecordingToPerformer,
    RecordingToSong,
    )

_sex_choices = (('', '- Select -'),
                ('female', 'Female'),
                ('male', 'Male')
               )

_genre_choices = (('', '- Select -'),
                  ('rock', 'Rock'),
                  ('pop', 'Pop'),
                  ('country', 'Country'),
                  ('jazz', 'Jazz'),
                  ('blues', 'Blues'),
                 )

class PerformerProfileSchema(Schema):
    """ Property schema for :class:`substanced.principal.User` objects.
    """
    display_name = colander.SchemaNode(
        colander.String(),
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
    favorite_genre = colander.SchemaNode(
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
        )
    )
@implementer(IPerformer)
class Performer(Folder):
    name = renamer()
    performer = reference_source_property(PerformerToUser)


class SongSchema(Schema):
    title = colander.SchemaNode(colander.String())
    artist = colander.SchemaNode(colander.String())
    timings = colander.SchemaNode(colander.String())


class SongPropertySheet(PropertySheet):
    schema = SongSchema()

class SongSchema(Schema):
    title = colander.SchemaNode(colander.String())
    artist = colander.SchemaNode(colander.String())
    timing = colander.SchemaNode(colander.String())


class SongPropertySheet(PropertySheet):
    schema = SongSchema()

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
    propertysheets=(('Basic', SongPropertySheet),),
    add_view='add_song'
    )
@implementer(ISong)
class Song(persistent.Persistent):

    creator_id = reference_sourceid_property(CreatorToSong)
    creator = reference_source_property(CreatorToSong)
    genre = None
    likes = 0

    def __init__(self, title='', artist='', timings='', stream=None):
        self.title = title
        self.artist = artist
        self.timings = timings
        self.blob = Blob()
        with self.blob.open("w") as fp:
            shutil.copyfileobj(stream, fp)

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
)
@implementer(IRecording)
class Recording(persistent.Persistent):
    performer = reference_source_property(RecordingToPerformer)
    song = reference_source_property(RecordingToSong)

    def __init__(self, tmpfolder):
        self.blob = None
        self.tmpfolder = tmpfolder

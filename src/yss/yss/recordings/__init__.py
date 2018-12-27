import persistent
import shutil

from zope.interface import implementer

from substanced.content import content
from substanced.event import subscribe_will_be_removed
from substanced.folder import Folder
from substanced.objectmap import multireference_target_property
from substanced.objectmap import multireference_targetid_property
from substanced.objectmap import reference_source_property

from yss.interfaces import (
    IRecording,
    IRecordings,
    PerformerLikesRecording,
    RecordingToPerformer,
    RecordingToSong,
    RelatedPropertySheet,
    )

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
    effects = ()
    musicvolume = 0

    def __init__(self, tmpfolder):
        self.dry_blob = None
        self.mixed_blob = None
        self.tmpfolder = tmpfolder

    @property
    def title(self):
        return getattr(self.song, 'title', 'Unknown')

    @property
    def genre(self):
        return getattr(self.song, 'genre', 'Unknown')

    @property
    def num_likes(self):
        return len(self.liked_by_ids)

@subscribe_will_be_removed(content_type='Recording')
def recording_will_be_removed(event):
    # delete tempfile data for recording when recording is deleted
    if event.moving is not None: # it's not really being removed
        return

    recording = event.object

    shutil.rmtree(recording.tmpfolder, ignore_errors=True)

def includeme(config):
    config.add_static_view('record', 'yss.recordings:static')

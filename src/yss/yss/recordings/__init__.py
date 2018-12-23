import persistent

from zope.interface import implementer

from substanced.content import content
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

    @property
    def title(self):
        return getattr(self.song, 'title', 'Unknown')

    @property
    def genre(self):
        return getattr(self.song, 'genre', 'Unknown')

    @property
    def num_likes(self):
        return len(self.liked_by_ids)

    def __init__(self, tmpfolder):
        self.blob = None
        self.tmpfolder = tmpfolder

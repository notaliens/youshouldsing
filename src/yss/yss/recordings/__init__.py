import audioread
import persistent
import shutil
import time


from BTrees.Length import Length
from zope.interface import implementer
from ZODB.blob import Blob

from substanced._compat import is_nonstr_iter
from substanced.content import content
from substanced.event import subscribe_will_be_removed
from substanced.folder import Folder
from substanced.objectmap import multireference_target_property
from substanced.objectmap import multireference_targetid_property
from substanced.objectmap import reference_source_property
from substanced.workflow import Workflow
from substanced.util import get_acl, set_acl, find_service

from pyramid.security import (
    Allow,
    Authenticated,
    Everyone,
    ALL_PERMISSIONS,
    DENY_ALL,
    )

from yss.interfaces import (
    IRecording,
    IRecordings,
    PerformerLikesRecording,
    RecordingToPerformer,
    RecordingToSong,
    RelatedPropertySheet,
    )

from yss.utils import get_redis, decode_redis_hash

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
    show_camera = True
    latency = 0
    voladjust = 0
    description = ''
    dry_duration = 0
    mixed_duration = 0
    remixing_duration = 0
    dry_blob = None
    remixing_blob = None
    mixed_blob = None
    enqueued = False
    numviews = 0
    _num_views = None

    def __init__(self, tmpfolder):
        self.tmpfolder = tmpfolder
        self._num_views = Length()

    @property
    def title(self):
        return getattr(self.song, 'title', 'Unknown')

    @property
    def genre(self):
        return getattr(self.song, 'genre', 'Unknown')

    @property
    def num_likes(self):
        return len(self.liked_by_ids)

    @property
    def num_views(self):
        if self._num_views is None:
            self._num_views = Length()
        return self._num_views

    @property
    def mixed(self):
        return bool(self.mixed_blob) and True or False

    @property
    def remixed(self):
        return bool(self.remixing_blob) and True or False

    @property
    def mixprogress_key(self):
        return f'mixprogress-{self.__oid__}'

    def enqueue(self, request):
        redis = get_redis(request)
        redis.hmset(self.mixprogress_key,
                    {'pct':0, 'status':'Enqueued'}
        )
        redis.rpush(
            "yss.new-recordings", f'{self.__oid__}|{time.time()}'
        )
        self.enqueued = True

    def get_mixprogress(self, request):
        redis = get_redis(request)
        progress = decode_redis_hash(
            redis.hgetall(self.mixprogress_key)
            )
        progress['done'] = not bool(self.enqueued)
        return progress

    def initialize(self, stream, request):
        self.set_unmixed(stream)

    def set_unmixed(self, stream):
        if self.dry_blob is None:
            self.dry_blob = Blob()
        if self.remixing_blob is None:
            self.remixing_blob = Blob()
        with self.dry_blob.open('w') as dry:
            with self.remixing_blob.open('w') as remixing:
                while True:
                    data = stream.read(1<<19) # 512K
                    if not data:
                        break
                    dry.write(data)
                    remixing.write(data)
        # cache duration for use in progress
        duration = audioread.audio_open(
            self.dry_blob._p_blob_uncommitted).duration
        # cache duration for use in progress
        self.dry_duration = duration
        self.remixing_duration = duration

    def set_remixing(self, stream):
        if self.remixing_blob is None:
            self.remixing_blob = Blob()
        with self.remixing_blob.open("w") as saveto:
            shutil.copyfileobj(stream, saveto)
        # cache duration for use in progress
        self.remixing_duration = audioread.audio_open(
            self.remixing_blob._p_blob_uncommitted).duration

    def set_mixed(self):
        if self.remixing_blob:
            self.mixed_blob = self.remixing_blob
            self.mixed_duration = self.remixing_duration
            del self.remixing_blob
            del self.remixing_duration


@subscribe_will_be_removed(content_type='Recording')
def recording_will_be_removed(event):
    # delete tempfile data for recording when recording is deleted
    if event.moving is not None: # it's not really being removed
        return

    recording = event.object

    shutil.rmtree(recording.tmpfolder, ignore_errors=True)

_PUBLISHED_ACL = [
    (Allow, Authenticated, ALL_PERMISSIONS),
    (Allow, Everyone, ('view',)),
]


def change_acl_callback(content, workflow, transition, request):
    new_acl = []
    current_acl = get_acl(content, [])
    admins = find_service(content, 'principals')['groups']['admins']
    recording = content
    performer = getattr(recording, 'performer', None)
    if performer is None:
        return # eyeroll, foil workflow initialization via subscriber
    user = performer.user
    owner_id = user.__oid__
    admins_id = admins.__oid__
    for ace in current_acl:
        # preserve all permissions defined by other subsystems (like "like")
        if ace == DENY_ALL:
            continue
        _, _, perms = ace
        if perms is ALL_PERMISSIONS:
            continue
        if not is_nonstr_iter(perms):
            perms = [perms]
        if 'view' in perms or 'yss.indexed' in perms or 'yss.edit' in perms:
            continue
        new_acl.append(ace)

    PRIVATE_ACES = [
        (Allow, admins_id, ALL_PERMISSIONS),
        (Allow, owner_id, ('view',)),
        (Allow, owner_id, ('yss.edit',)),
        DENY_ALL,
        ]

    if transition:
        # if not initial state
        if transition['name'].startswith('Make public'):
            new_acl.extend([
                (Allow, Everyone, ('view',)),
                (Allow, Everyone, ('yss.indexed',)),
                (Allow, owner_id, ('yss.edit',)),
            ])
        if transition['name'].startswith('Make private'):
            new_acl.extend(PRIVATE_ACES)
        if transition['name'].startswith('Make authenticated-only'):
            new_acl.extend([
                (Allow, admins_id, ALL_PERMISSIONS),
                (Allow, 'system.Authenticated', ('view',)),
                (Allow, 'system.Authenticated', ('yss.indexed',)),
                (Allow, owner_id, ('yss.edit',)),
                DENY_ALL,
            ])
    else:
        # initial state
        new_acl.extend(PRIVATE_ACES)

    set_acl(content, new_acl)

workflow = Workflow(initial_state='Private', type='Visibility')
workflow.add_state('Private', callback=change_acl_callback)
workflow.add_state('Public', callback=change_acl_callback)
workflow.add_state('Authenticated Only', callback=change_acl_callback)
workflow.add_transition(
    'Make public (from private)',
    from_state='Private',
    to_state='Public',
)
workflow.add_transition(
    'Make public (from authenticated-only)',
    from_state='Authenticated Only',
    to_state='Public',
)
workflow.add_transition(
    'Make private (from authenticated-only)',
    from_state='Authenticated Only',
    to_state='Private',
)
workflow.add_transition(
    'Make private (from public)',
    from_state='Public',
    to_state='Private',
)
workflow.add_transition(
    'Make authenticated-only (from public)',
    from_state='Public',
    to_state='Authenticated Only',
)
workflow.add_transition(
    'Make authenticated-only (from private)',
    from_state='Private',
    to_state='Authenticated Only',
)

def includeme(config):
    config.add_static_view('recordingstatic', 'yss.recordings:static')
    config.add_workflow(workflow, ('Recording',))

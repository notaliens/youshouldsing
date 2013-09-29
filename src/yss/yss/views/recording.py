import base64
import os
import random
import shutil

from pyramid.response import FileResponse
from pyramid.traversal import resource_path
from pyramid.view import view_config

from ..utils import get_redis


random.seed()


@view_config(content_type='Song',
             name="record",
             renderer="templates/record.pt")
def recording_app(song, request):
    recording_id = generate_recording_id({})
    return {
        "id": recording_id,
        "mp3_url": request.resource_url(song, 'mp3'),
        "timings": song.timings,
    }


@view_config(content_type='Song', name="record", xhr=True, renderer='string')
def save_audio(song, request):
    f = request.params['data'].file
    id = request.params['id']
    fname = request.params['filename']
    tmpdir = '/tmp/' + id
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    with open('%s/%s' % (tmpdir, fname), 'wb') as output:
        shutil.copyfileobj(f, output)
    return 'OK'


@view_config(content_type='Song', name="record", xhr=True, renderer='string',
             request_param='framedata')
def save_video(song, request):
    id = request.params['id']
    tmpdir = '/tmp/' + id
    fname = os.path.join(tmpdir, 'frame%d.png')
    for i, data in enumerate(request.params.getall('framedata')):
        preamble = 'data:image/png;base64,'
        assert data.startswith(preamble), data
        data = base64.b64decode(data[len(preamble):])
        with open(fname % i, 'wb') as fp:
            fp.write(data)
    return 'OK'


@view_config(content_type='Song', name="record", xhr=True, renderer='string',
             request_param='finished')
def finish_recording(song, request):
    tmpdir = '/tmp/' + request.params['id']
    recording = request.registry.content.create('Recording', tmpdir)
    recordings = request.root['recordings']
    name = generate_recording_id(recordings)
    recordings[name] = recording
    recording.performer = request.user.performer
    recording.song = song

    redis = get_redis(request)
    print "finished", tmpdir, resource_path(recording)
    redis.rpush("yss.new-recordings", resource_path(recording))
    return request.resource_url(recording)


idchars = (
    map(chr, range(ord('a'), ord('z') + 1)) +
    map(chr, range(ord('A'), ord('Z') + 1)) +
    map(chr, range(ord('0'), ord('9') + 1)))


def generate_recording_id(recordings):
    while True:
        id = ''.join([random.choice(idchars) for _ in range(8)])
        if id not in recordings:
            break
    return id


@view_config(
    content_type='Song',
    name='mp3',
    #permission=???RETAIL_VIEW???
)
def stream_mp3(song, request):
    return FileResponse(
        song.blob.committed(),
        content_type='audio/mpeg')

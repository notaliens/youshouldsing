import base64
import os
import random
import shutil

from pyramid.httpexceptions import HTTPBadRequest
from pyramid.response import FileResponse
from pyramid.traversal import resource_path
from pyramid.view import view_config
from pyramid.settings import asbool

from substanced.util import (
    find_index,
    Batch,
    )

from substanced.folder.views import generate_text_filter_terms

from ..utils import get_redis

from ..interfaces import (
    IRecording,
    IRecordings,
    )


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
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
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
    print request.user.performer
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


class RecordingView(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @view_config(context=IRecording, renderer='templates/recording.pt')
    def __call__(self):
        recording = self.context
        return {
            'title':recording.title,
            'performer':recording.performer,
            'likes':len(recording.liked_by),
            'liked_by': recording.liked_by,
            'recordings':[],
            'video_url': self.request.resource_url(recording, 'movie'),
            'processed': bool(recording.blob),
            }

@view_config(
    content_type='Recording',
    name='movie')
def stream_movie(recording, request):
    return FileResponse(
        recording.blob.committed(),
        content_type='video/ogg'
        )


class RecordingsView(object):
    default_sort = 'performer'
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def query(self):
        request = self.request
        context = self.context
        q = find_index(context, 'system', 'content_type').eq('Recording')
        q = q & find_index(context, 'system', 'allowed').allows(
            request, 'view')
        filter_text = request.params.get('filter_text')
        if filter_text:
            terms = generate_text_filter_terms(filter_text)
            text = find_index(context, 'system', 'text')
            for term in terms:
                if text.check_query(term):
                    q = q & text.eq(term)
        filter_genre = request.params.get('filter_genre')
        if filter_genre:
            q = q & find_index(context, 'yss', 'genre').eq(filter_genre)
        resultset = q.execute()
        sorting = request.params.get('sorting')
        reverse = request.params.get('reverse')
        if reverse == 'false':
            reverse = False
        reverse = bool(reverse)
        if sorting:
            resultset = self.sort_by(resultset, sorting, reverse)
        else:
            resultset = self.sort_by(resultset, self.default_sort, False)
        return resultset

    def sort_by(self, rs, token, reverse):
        context = self.context
        title = find_index(context, 'yss', 'title')
        performer = find_index(context, 'yss', 'performer')
        likes = find_index(context, 'yss', 'likes')
        genre = find_index(context, 'yss', 'genre')
        created = find_index(context, 'yss', 'created')
        sorting = {
            'date':(created, likes, title, performer, genre),
            'title':(title, performer, likes, genre, created),
            'performer':(performer, title, likes, genre, created),
            'genre':(genre, performer, title, likes, created),
            'likes':(likes, performer, title, genre, created),
            }
        indexes = sorting.get(token, sorting[self.default_sort])
        for idx in indexes[1:]:
            rs = rs.sort(idx)
        first = indexes[0]
        rs = rs.sort(first, reverse=reverse)
        return rs

    @view_config(context=IRecordings, renderer='templates/recordings.pt')
    def contents(self):
        request = self.request
        resultset = self.query()
        batch = Batch(resultset, self.request, seqlen=len(resultset),
                      default_size=100)
        return {
            'batch':batch,
            'filter_text':request.params.get('filter_text'),
            'reverse':request.params.get('reverse', 'false')
            }

    def sort_tag(self, token):
        request = self.request
        context = self.context
        reverse = request.params.get('reverse', 'false')
        reverse = asbool(reverse)
        sorting = request.params.get('sorting')
        if sorting == token or (not sorting and token == self.default_sort):
            if reverse:
                icon = 'glyphicon glyphicon-chevron-up'
            else:
                icon = 'glyphicon glyphicon-chevron-down'
            reverse = reverse and 'false' or 'true'
        else:
            icon = ''
            reverse = 'false'

        url = request.resource_url(
            context, query=(
                ('sorting', token), ('reverse', reverse)
                )
            )
        return '<a href="%s">%s <i class="%s"> </i></a>' % (
            url,
            token.capitalize(),
            icon
            )

@view_config(
    context=IRecording,
    name='like',
    renderer='json',
)
def like_recording(context, request):
    performer = request.user.performer
    if performer in context.liked_by:
        raise HTTPBadRequest("Already")
    context.liked_by.connect([performer])
    return {'ok': True,
            'likes': context.likes,
            }

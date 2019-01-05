import colander
import deform.widget
import logging
import os
import random
import slug
import shutil

from ZODB.blob import Blob

from pyramid.httpexceptions import HTTPBadRequest
from pyramid.settings import asbool
from pyramid.httpexceptions import HTTPFound
from pyramid.traversal import (
    find_root,
    resource_path,
    )
from pyramid.decorator import reify
from pyramid.view import (
    view_config,
    view_defaults,
    )

from substanced.file import FileNode
from substanced.form import FormView
from substanced.folder.views import generate_text_filter_terms
from substanced.schema import Schema
from substanced.sdi import mgmt_view

from substanced.util import (
    Batch,
    find_index,
    )
from substanced.workflow import get_workflow

from yss.interfaces import (
    ISongs,
    ISong,
    )
from yss.utils import (
    get_redis,
    decode_redis_hash,
    format_timings,
    )

known_effects = (
    'effect-reverb',
    'effect-chorus',
    )

idchars = (
    list(map(chr, range(ord('a'), ord('z') + 1))) +
    list(map(chr, range(ord('A'), ord('Z') + 1))) +
    list(map(chr, range(ord('0'), ord('9') + 1))))

logger = logging.getLogger('yss')

@view_defaults(context=ISongs)
class SongsView(object):

    default_sort = 'title'
    batch_size = 20

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def query(self):
        request = self.request
        context = self.context
        q = find_index(context, 'system', 'content_type').eq('Song')
        q = q & find_index(context, 'system', 'allowed').allows(
            request, 'yss.indexed')
        filter_text = request.params.get('filter_text')
        if filter_text:
            terms = generate_text_filter_terms(filter_text)
            lyrics = find_index(context, 'yss', 'lyrics')
            # depends on artist and song name being in lyrics, probably
            # not tenable and must create a more generic yss-specific
            # generic text index that includes, artist, song title,
            # and lyrics
            for term in terms:
                if lyrics.check_query(term):
                    q = q & lyrics.eq(term)

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
        artist = find_index(context, 'yss', 'artist')
        num_likes = find_index(context, 'yss', 'num_likes')
        num_recordings = find_index(context, 'yss', 'num_recordings')
        genre = find_index(context, 'yss', 'genre')
        created = find_index(context, 'yss', 'created')
        duration = find_index(context, 'yss', 'duration')
        sorting = {
            'date':
            (created, num_recordings, num_likes, title, artist, genre),
            'title':
            (title, artist, num_recordings, num_likes, genre, created),
            'artist':
            (artist, title, num_recordings, num_likes, genre, created),
            'genre':
            (genre, artist, title, num_recordings, num_likes, created),
            'num_likes':
            (num_likes, artist, title, num_recordings, genre, created),
            'recordings':
            (num_recordings, artist, title, num_likes, genre, created),
            'duration':
            (duration, artist, title, genre, created, num_likes,num_recordings),
            }
        indexes = sorting.get(token, sorting[self.default_sort])
        for idx in indexes[1:]:
            rs = rs.sort(idx)
        first = indexes[0]
        rs = rs.sort(first, reverse=reverse)
        return rs

    @view_config(renderer='templates/songs.pt')
    def contents(self):
        request = self.request
        resultset = self.query()
        batch = Batch(resultset, self.request, seqlen=len(resultset),
                      default_size=self.batch_size)
        return {
            'batch':batch,
            'filter_text':request.params.get('filter_text'),
            'reverse':request.params.get('reverse', 'false')
            }

    def sort_tag(self, token, title):
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
            title,
            icon,
            )

    @mgmt_view(name='preview')
    def preview(self):
        return HTTPFound(location=self.request.resource_url(self.context))


@view_defaults(context=ISong)
class SongView(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @reify
    def has_retime_permission(self):
        song = self.context
        return self.request.has_permission('yss.retime', song)

    def tabs(self):
        state = self.request.view_name
        song = self.context
        tabs = []
        if self.has_retime_permission:
            tabs.append(
                {'title':'View',
                 'id':'button-view',
                 'url':self.request.resource_url(song),
                 'class':state == '' and 'active' or '',
                 'enabled':True,
                 })
            tabs.append(
                {'title':'Record',
                 'id':'button-recordview',
                 'url':self.request.resource_url(song, 'record'),
                 'class':state=='record' and 'active' or '',
                 'enabled':True,
                 })
            tabs.append(
                {'title':'Retime',
                 'id':'button-retime',
                 'url':self.request.resource_url(song, 'retime'),
                 'class':state == 'retime' and 'active' or '',
                 'enabled':True,
                 })
        return tabs

    @view_config(
        renderer='templates/song.pt',
        permission='view'
    )
    def view(self):
        song = self.context
        return {
            'title':song.title,
            'artist':song.artist,
            'num_likes':song.num_likes,
            'liked_by': song.liked_by,
            'recordings':song.recordings,
            'can_record':self.request.has_permission('yss.record', song),
            'can_retime':self.has_retime_permission,
            }

    @view_config(
        name='like',
        renderer='json',
        permission='yss.like',
    )
    def like(self):
        request = self.request
        performer = request.user.performer
        if performer in self.context.liked_by:
            raise HTTPBadRequest("Already")
        self.context.liked_by.connect([performer])
        return {'ok': True,
                'num_likes': self.context.num_likes,
                'can_like':request.layout_manager.layout.can_like(performer),
               }

    @view_config(
        name='unlike',
        renderer='json',
        permission='yss.like',
    )
    def unlike(self):
        request = self.request
        performer = request.user.performer
        if performer in self.context.liked_by:
            self.context.liked_by.disconnect([performer])
        return {'ok': True,
                'num_likes': self.context.num_likes,
                'can_like':request.layout_manager.layout.can_like(performer),
               }

    @view_config(
        name='retime',
        permission='yss.retime',
        renderer='templates/retime.pt',
    )
    def retime(self):
        timings = getattr(self.context, 'alt_timings', '').strip()
        if not timings:
            timings = self.context.timings.strip()
        formatted_timings = format_timings(timings)
        if self.context.retiming:
            processed = 0
        else:
            processed = 1
        return {
            "mp3_url": self.request.resource_url(self.context, 'mp3'),
            "timings": timings,
            "formatted_timings":formatted_timings,
            'processed':processed,
        }

    @view_config(
        name='finish_retime',
        permission='yss.retime',
        xhr=True,
        renderer='string',
    )
    def finish_retime(self):
        file_stream = self.request.params['data'].file

        song = self.context
        song.retiming = True
        song.retiming_blob = Blob()

        with song.retiming_blob.open("w") as saveto:
            shutil.copyfileobj(file_stream, saveto)

        redis = get_redis(self.request)
        redis.rpush("yss.new-retimings", resource_path(self.context))
        return self.request.resource_url(self.context, 'retime')

    @view_config(
        name='retimeprogress',
        renderer='json',
        permission='view',
    )
    def retimeprogress(self):
        redis = get_redis(self.request)
        song = self.context
        progress = decode_redis_hash(
            redis.hgetall(f'retimeprogress-{self.context.__name__}')
            )
        progress['done'] = not song.retiming and 1 or 0
        return progress

    @view_config(
        name='mp3',
        permission='view',
    )
    def stream_mp3(self):
        return self.context.get_response(request=self.request)

    @view_config(
        name="record",
        renderer="templates/record.pt",
        permission='view', # XXX
    )
    def recording_app(self):
        song = self.context
        root = find_root(song)
        return {
            "mp3_url": self.request.resource_url(song, 'mp3'),
            "timings": song.timings,
            "max_framerate": root.max_framerate,
        }

    @view_config(
        name="record",
        xhr=True,
        renderer='string',
        request_param='finished',
        permission='yss.record',
    )
    def finish_recording(self):
        song = self.context
        request = self.request
        recordings = find_root(song)['recordings']
        recording_id = generate_recording_id(recordings)
        f = request.params['data'].file
        tmpdir = get_recording_tempdir(request, recording_id)
        recording = request.registry.content.create('Recording', tmpdir)
        recordings[recording_id] = recording
        performer = request.user.performer
        recording.performer = performer
        recording.song = song
        recording.dry_blob = Blob()
        recording.effects = tuple([ # not currently propsheet-exposed
            x for x in request.params.getall('effects') if x in known_effects
        ])
        try:
            musicvolume = float(request.params['musicvolume'])
            if (musicvolume < 0) or (musicvolume > 1):
                raise TypeError
            recording.musicvolume = musicvolume
        except (TypeError, ValueError):
            # use default musicvolume of 0 set at class level
            pass
        description = request.params['description'][:5000]
        recording.description = description
        with recording.dry_blob.open("w") as saveto:
            shutil.copyfileobj(f, saveto)
        workflow = get_workflow(request, 'Visibility', 'Recording')
        workflow.reset(recording, request) # private by default
        visibility = request.params.get('visibility', 'Private')
        workflow.transition_to_state(recording, request, visibility)
        redis = get_redis(request)
        redis.rpush("yss.new-recordings", resource_path(recording))
        print ("finished", tmpdir, resource_path(recording))
        return request.resource_url(recording)


class AddSongSchema(Schema):
    title = colander.SchemaNode(colander.String())
    artist = colander.SchemaNode(colander.String())
    lyrics = colander.SchemaNode(
        colander.String(),
        widget = deform.widget.TextAreaWidget(style='height: 200px'),
    )
    timings = colander.SchemaNode(
        colander.String(),
        widget = deform.widget.TextAreaWidget(style='height: 200px'),
        )
    file = FileNode()

@mgmt_view(
    context=ISongs,
    name='add_song',
    tab_title='Add Song',
    permission='sdi.add-content',
    renderer='substanced.sdi:templates/form.pt',
    tab_condition=False
    )
class AddSongView(FormView):
    title = 'Add Song'
    schema = AddSongSchema()
    buttons = ('add',)

    def add_success(self, appstruct):
        title = appstruct['title']
        artist = appstruct['artist']
        timings = appstruct['timings']
        lyrics = appstruct['lyrics']
        name = slug.slug(title)
        stream = appstruct['file']['fp']
        song = self.request.registry.content.create(
            'Song',
            title,
            artist,
            lyrics,
            timings,
            stream
            )
        self.context[name] = song
        return HTTPFound(self.request.sdiapi.mgmt_path(self.context))

def generate_recording_id(recordings):
    while True:
        id = ''.join([random.choice(idchars) for _ in range(8)])
        if id not in recordings:
            break
    return id

def get_recording_tempdir(request, recording_id):
    postproc_dir = request.registry.settings['yss.postproc_dir']
    if set(recording_id).difference(set(idchars)):
        # don't allow filesystem shenanigans if we accept this from a client
        raise RuntimeError('bad recording id')
    return os.path.abspath(os.path.join(postproc_dir, recording_id))

def get_retime_tempdir(request, song_id):
    retime_dir = request.registry.settings['yss.retime_dir']
    return os.path.abspath(os.path.join(retime_dir, song_id))

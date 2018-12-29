import colander
import deform.widget
import logging
import os
import random
import slug
import shutil

from sh import ffmpeg

from google.cloud import storage
from google.cloud import speech
from google.cloud.speech import enums as speech_enums
from google.cloud.speech import types as speech_types

from ZODB.blob import Blob

from pyramid.httpexceptions import HTTPBadRequest
from pyramid.settings import asbool
from pyramid.httpexceptions import HTTPFound
from pyramid.traversal import (
    find_root,
    resource_path,
    )
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

from yss.interfaces import (
    ISongs,
    ISong,
    )
from yss.utils import get_redis

random.seed()

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
            request, 'view')
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

    @view_config(
        renderer='templates/song.pt',
        permission='view'
    )
    def __call__(self):
        song = self.context
        return {
            'title':song.title,
            'artist':song.artist,
            'num_likes':song.num_likes,
            'liked_by': song.liked_by,
            'recordings':song.recordings,
            'can_record':self.request.has_permission('yss.record', song),
            'can_retime':self.request.has_permission('yss.retime', song),
            }

    @view_config(
        name='like',
        renderer='json',
        permission='yss.like',
    )
    def like(self):
        performer = self.request.user.performer
        if performer in self.context.liked_by:
            raise HTTPBadRequest("Already")
        self.context.liked_by.connect([performer])
        return {'ok': True,
                'num_likes': self.context.num_likes,
               }

    @view_config(
        name='retime',
        permission='yss.retime',
        renderer='templates/retime.pt',
    )
    def retime(self):
        timings = getattr(self.context, 'alt_timings', None)
        if timings is None:
            timings = self.context.timings
        formatted_timings = format_timings(timings)
        return {
            "mp3_url": self.request.resource_url(self.context, 'mp3'),
            "timings": timings,
            "formatted_timings":formatted_timings,
        }

    @view_config(
        name='finish_retime',
        permission='yss.retime',
        xhr=True,
        renderer='string',
    )
    def finish_retime(self):
        gproject = os.environ['YSS_GOOGLE_STORAGE_PROJECT']
        gbucket = os.environ['YSS_GOOGLE_STORAGE_BUCKET']
        blobname = f'{self.context.__name__}.retime' # XXX simultaneous retimes
        gsuri = f'gs://{gbucket}/{blobname}'

        file_stream = self.request.params['data'].file

        tmpdir = get_retime_tempdir(self.request, self.context.__name__) # XXX
        try:
            os.makedirs(tmpdir)
        except FileExistsError:
            pass
        webm_filename = os.path.join(tmpdir, 'retime.webm')
        opus_filename = os.path.join(tmpdir, 'retime.opus')

        logger.info('Converting webm to opus') # XX should just copy audio

        with open(webm_filename, 'wb') as saveto:
            shutil.copyfileobj(file_stream, saveto)

        ffmpeg(
            "-y",
            "-i", webm_filename,
            "-vn", # no video
            "-ar", "48000",
            "-y", # clobber
            opus_filename,
            )

        logger.info('Finished converting webm to opus')

        client = storage.Client(gproject)
        bucket = client.bucket(gbucket)
        blob = bucket.blob(blobname)
        logger.info('Uploading timing track to gcloud...')
        blob.upload_from_file(
            open(opus_filename, 'rb'),
            content_type='audio/opus',
        )
        logger.info('Finished uploading timing track...')

        client = speech.SpeechClient()

        audio = speech_types.RecognitionAudio(uri=gsuri)
        config = speech_types.RecognitionConfig(
            encoding=speech_enums.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=48000,
            language_code='en-US',
            enable_word_time_offsets=True,
        )

        operation = client.long_running_recognize(config, audio)
        # google.api_core.exceptions.GoogleAPICallError: None
        # Unexpected state: Long-running operation had neither response
        # nor error set.

        logger.info('Waiting for speech recognition operation to complete...')
        response = operation.result(timeout=90)
        logger.info('Speech recognition operation completed')

        timings = speech_results_to_timings(response.results, 7)
        self.context.alt_timings = timings

        return self.request.resource_url(self.context, 'retime')

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
        recording.performer = request.user.performer
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
        with recording.dry_blob.open("w") as saveto:
            shutil.copyfileobj(f, saveto)
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

def format_timings(timings):
    formatted = []
    twodecs = '%.2f'
    for start, end, words in timings:
        formatted_start = twodecs % start
        formatted_end = twodecs % end
        formatted_words = []
        for wordstart, word in words:
            formatted_words.append(
                [twodecs % wordstart,
                 word]
                )
        formatted.append([formatted_start, formatted_end, formatted_words])
    import pprint
    return pprint.pformat(formatted, width=50)

def get_retime_tempdir(request, song_id):
    retime_dir = request.registry.settings['yss.retime_dir']
    return os.path.abspath(os.path.join(retime_dir, song_id))

def speech_results_to_timings(speech_results, max_words_per_line):
    # Each result is for a consecutive portion of the audio. Iterate through
    # them to get the transcripts for the entire audio file.
    timings = []
    words = []
    for result in speech_results:
        # we'd like to be able to get hints about where lines end
        # naturally by relying on this result batching, but let's get it
        # working first
        words.extend(result.alternatives[0].words)

    line_start = 0
    word_end = 0
    word_timings = []

    for i, word in enumerate(words):
        start_secs = word.start_time.seconds
        start_ns = word.start_time.nanos
        start_ms = round(start_ns/1e+9, 3)
        word_start = start_secs + start_ms
        padding = ' '
        if line_start is None:
            line_start = word_start
            padding = ''
        end_secs = word.end_time.seconds
        end_ns = word.end_time.nanos
        end_ms = round(end_ns/1e+9, 3)
        word_end = end_secs + end_ms

        word_timings.append([word_start - line_start, padding + word.word])

        needs_line_break = i and (i % max_words_per_line == 0)

        if needs_line_break:
            timing = [line_start, word_end, word_timings]
            timings.append(timing)
            line_start = None
            word_timings = []

    timings.append([line_start, word_end, word_timings]) # stragglers

    return timings

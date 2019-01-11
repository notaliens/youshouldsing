import colander
import deform.widget
import ffmpeg
import hashlib
import logging
import os
import random
import slug
import shutil
import uuid

from ZODB.blob import Blob

from pyramid.httpexceptions import HTTPBadRequest
from pyramid.settings import asbool
from pyramid.httpexceptions import HTTPFound
from pyramid.decorator import reify
from pyramid.traversal import (
    find_root,
    resource_path,
    )
from pyramid.security import (
    Allow,
    Deny,
    Everyone,
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
    find_catalog,
    set_acl,
    get_acl,
    )
from substanced.workflow import get_workflow

from yss.interfaces import (
    ISongs,
    ISong,
    genre_choices,
    language_choices,
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
            text = find_index(context, 'yss', 'text')
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
            'num_recordings':
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

        query = [
            ('sorting', token), ('reverse', reverse)
        ]
        filter_text = request.params.get('filter_text')

        if filter_text:
            query.append(
                ('filter_text', filter_text)
                )

        url = request.resource_url(context, query=query)

        return '<a href="%s">%s <i class="%s"> </i></a>' % (
            url,
            title,
            icon,
            )

    @view_config(
        name='upload',
        renderer='templates/upload.pt',
        permission='yss.upload',
    )
    def upload(self):
        context = self.context
        request = self.request
        schema = SongUploadSchema().bind(request=request, context=context)
        form = deform.Form(schema, buttons=('Save',))
        rendered = None
        if 'Save' in request.POST:
            controls = request.POST.items()
            try:
                appstruct = form.validate(controls)
            except deform.ValidationFailure as e:
                rendered = e.render()
            else:
                audio_file = appstruct['audio_file']
                tmpdir = request.registry.settings['substanced.uploads_tempdir']
                job = uuid.uuid4().hex
                jobdir = os.path.join(tmpdir, job)
                try:
                    try:
                        os.makedirs(jobdir)
                    except FileExistsError:
                        pass
                    inputfn = os.path.join(jobdir, 'inputfile')
                    inputfile = open(inputfn, 'wb')
                    fp = audio_file['fp']
                    fp.seek(0)
                    shutil.copyfileobj(fp, inputfile)
                    M = 1024 * 1024 * 1024
                    md5 = hashlib.md5()
                    f = open(inputfn, 'rb')
                    while True:
                        data = f.read(M)
                        if not data:
                            break
                        md5.update(data)
                    opus_filename = os.path.join(jobdir, 'output.opus')
                    ffmpeg.input(inputfn).output(
                        opus_filename, ar=48000).run()
                    song = request.registry.content.create(
                        'Song',
                        appstruct['title'],
                        appstruct['artist'],
                        appstruct['lyrics'],
                        timings='',
                        audio_stream=open(opus_filename, 'rb'),
                        audio_mimetype='audio/opus',
                        language=appstruct['language'],
                    )
                finally:
                    shutil.rmtree(jobdir, ignore_errors=True)
                request.session.flash(
                    'Song uploaded. Now voice lyrics like William Shatner in '
                    'rhythm with the song in order to time the karaoke '
                    'display text.',
                    'info')
                song.language = appstruct['language']
                song.genre = appstruct['genre']
                song.year = appstruct['year']
                songname = slug.slug(appstruct['title'])
                hashval = md5.hexdigest()
                songname = f'{songname}-{hashval}'
                if songname in self.context:
                    request.session.flash('this song has already been uploaded')
                    raise HTTPFound(request.resource_url(self.context))
                self.context[songname] = song
                song.uploader = request.performer # NB must be after seating
                set_acl(song,
                        [
                            (Allow, request.user.__oid__, ['yss.edit']),
                            (Deny, Everyone, ['yss.indexed']),
                        ]
                )
                return HTTPFound(request.resource_url(song, '@@retime'))
        else:
            appstruct = {
                'title':colander.null,
                'artist':colander.null,
                'audio_file':colander.null,
                'genre':colander.null,
                'language':colander.null,
                'lyrics':colander.null,
                'year':colander.null,
                }
        if rendered is None:
            rendered = form.render(appstruct, readonly=False)
        return {'form':rendered}

    def tabs(self):
        songs = self.context
        request = self.request
        state = request.view_name
        tabs = []
        if request.has_permission('yss.upload', songs):
            tabs.append(
                {'title':'View',
                 'id':'button-view',
                 'url':request.resource_url(songs),
                 'class':state == '' and 'active' or '',
                 'enabled':True,
                 })
            tabs.append(
                {'title':'Upload',
                 'id':'button-upload',
                 'url':request.resource_url(songs, '@@upload'),
                 'class':state == 'upload' and 'active' or '',
                 'enabled':True,
                 })
        return tabs

    @mgmt_view(name='preview')
    def preview(self):
        return HTTPFound(location=self.request.resource_url(self.context))


@view_defaults(context=ISong)
class SongView(object):
    default_sort = 'created'
    batch_size = 20
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @reify
    def has_edit_permission(self):
        song = self.context
        return self.request.has_permission('yss.edit', song)

    @reify
    def has_record_permission(self):
        song = self.context
        return self.request.has_permission('yss.record', song)

    def tabs(self):
        state = self.request.view_name
        song = self.context
        tabs = []
        tabs.append(
            {'title':'Listen',
             'id':'button-view',
             'url':self.request.resource_url(song),
             'class':state == '' and 'active' or '',
             'enabled':True,
            })
        if self.has_record_permission:
            tabs.append(
                {'title':'Record',
                 'id':'button-recordview',
                 'url':self.request.resource_url(song, '@@record'),
                 'class':state=='record' and 'active' or '',
                 'enabled':True,
                 })
        if len(song.recording_ids):
            tabs.append(
                {'title':'Recordings',
                 'id':'button-recordings',
                 'url':self.request.resource_url(song, '@@recordings'),
                 'class':state == 'recordings' and 'active' or '',
                 'enabled':True,
                })

        if self.has_edit_permission:
            tabs.append(
                {'title':'Retime',
                 'id':'button-retime',
                 'url':self.request.resource_url(song, '@@retime'),
                 'class':state == 'retime' and 'active' or '',
                 'enabled':True,
                 })
            tabs.append(
                {'title':'Edit',
                 'id':'button-edit',
                 'url':self.request.resource_url(song, '@@edit'),
                 'class':state == 'edit' and 'active' or '',
                 'enabled':True,
                 })
        return tabs

    @view_config(
        renderer='templates/song.pt',
        permission='view'
    )
    def view(self):
        song = self.context
        song = self.context
        root = find_root(song)
        return {
            'title':song.title,
            'artist':song.artist,
            'num_likes':song.num_likes,
            'liked_by': song.liked_by,
            'recordings':song.recordings,
            'can_record':self.has_record_permission,
            'can_retime':self.has_edit_permission,
            "stream_url": self.request.resource_url(song, '@@stream'),
            "timings": song.timings,
            "max_framerate": root.max_framerate,
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
        permission='yss.edit',
        renderer='templates/retime.pt',
    )
    def retime(self):
        alt_timings = getattr(self.context, 'alt_timings', '').strip()
        timings = alt_timings.strip()
        if not timings:
            timings = self.context.timings.strip()
        if not timings:
            timings = '[]'
        formatted_timings = format_timings(timings)
        if self.context.retiming:
            processed = 0
        else:
            processed = 1
        return {
            "stream_url": self.request.resource_url(self.context, '@@stream'),
            "timings": timings,
            "formatted_timings":formatted_timings,
            'processed':processed,
            'accept_url':self.request.resource_url(
                self.context, '@@accept_retime'
            ),
            'needs_accept':int(bool(alt_timings)),
            'lyrics':self.context.lyrics,
        }

    @view_config(
        name='finish_retime',
        permission='yss.edit',
        xhr=True,
        renderer='string',
    )
    def finish_retime(self):
        request = self.request
        file_stream = self.request.params['data'].file

        song = self.context
        song.retiming = True
        song.retiming_blob = Blob()

        with song.retiming_blob.open("w") as saveto:
            shutil.copyfileobj(file_stream, saveto)

        redis = get_redis(self.request)
        redis.rpush("yss.new-retimings", resource_path(self.context))
        set_acl(song,
                [
                    (Allow, request.user.__oid__, ['yss.edit']),
                    (Deny, Everyone, ['yss.indexed']),
                ]
        )
        self.request.session.flash(
            'This is gonna take a while. It\'s not magic. But after the '
            'retiming is done processing, listen and watch to see that your '
            'spoken lyrics line up with the song acceptably, and hit accept if '
            'you are happy with the result. Remember: it\'s just karaoke.',
            'info')
        return self.request.resource_url(self.context, '@@retime')

    @view_config(
        name='accept_retime',
        permission='yss.edit',
        xhr=True,
        renderer='string',
    )
    def accept_retime(self):
        song = self.context
        song.timings = song.alt_timings
        song.alt_timings = ''
        new_acl = []
        acl = get_acl(song)
        for ace in acl:
            if ace[0] == Deny and ace[2] == ['yss.indexed']:
                continue
            new_acl.append(ace)
        set_acl(song, new_acl)
        self.request.session.flash(
            'Retime accepted, song will show up in searches, and may now be '
            'recorded by everyone. Nice work.', 'info')
        return self.request.resource_url(self.context, '@@retime')

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
        name='stream',
        permission='view',
    )
    def stream(self):
        return self.context.get_response(request=self.request)

    @view_config(
        name="record",
        renderer="templates/record.pt",
        permission='yss.record',
    )
    def record(self):
        song = self.context
        root = find_root(song)
        return {
            "stream_url": self.request.resource_url(song, '@@stream'),
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
        performer = self.request.user.performer
        recordings = performer['recordings']
        recording_id = self.generate_recording_id(recordings)
        f = request.params['data'].file
        # disallow /, .., etc
        sane_name = ''.join(c for c in performer.__name__ if c.isalnum())
        tmpdir_name = f'{sane_name}-{recording_id}'
        tmpdir = get_recording_tempdir(request, tmpdir_name)
        recording = request.registry.content.create('Recording', tmpdir)
        description = request.params['description'][:5000]
        recording.description = description
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
        with recording.dry_blob.open("w") as saveto:
            shutil.copyfileobj(f, saveto)
        workflow = get_workflow(request, 'Visibility', 'Recording')
        workflow.reset(recording, request) # private by default
        visibility = request.params.get('visibility', 'Private')
        workflow.transition_to_state(recording, request, visibility)
        # reindex visibility state and other stuff for good measure
        catalog = find_catalog(recording, 'yss')
        catalog.reindex_resource(recording)
        redis = get_redis(request)
        redis.rpush("yss.new-recordings", resource_path(recording))
        print ("finished", tmpdir, resource_path(recording))
        return request.resource_url(recording)

    def generate_recording_id(self, recordings):
        i = 0
        while True:
            id = ''.join([random.choice(idchars) for _ in range(8)])
            if id not in recordings:
                break
            i+=1
        return id

    @view_config(
        name='edit',
        renderer='templates/edit.pt',
        permission='yss.edit',
    )
    def edit(self):
        context = self.context
        request = self.request
        schema = SongEditSchema().bind(request=request, context=context)
        form = deform.Form(schema, buttons=('Save',))
        rendered = None
        if 'Save' in request.POST:
            controls = request.POST.items()
            try:
                appstruct = form.validate(controls)
            except deform.ValidationFailure as e:
                rendered = e.render()
            else:
                context.title = appstruct['title']
                context.artist = appstruct['artist']
                context.genre = appstruct['genre']
                context.language = appstruct['language']
                context.lyrics = appstruct['lyrics']
                context.year = appstruct['year']
                find_catalog(context, 'yss').reindex_resource(context)
                find_catalog(context, 'system').reindex_resource(context)
                request.session.flash('Song edited.', 'info')
                return HTTPFound(request.resource_url(context, '@@edit'))
        else:
            appstruct = {
                'title':context.title,
                'artist':context.artist,
                'genre':context.genre,
                'language':context.language,
                'lyrics':context.lyrics,
                'year':context.year,
                }
        if rendered is None:
            rendered = form.render(appstruct, readonly=False)
        return {'form':rendered}

    @view_config(
        name="recordings",
        renderer="templates/recordings.pt",
        permission='view',
    )
    def recordings(self):
        request = self.request
        resultset = self.query()
        batch = Batch(resultset, self.request, seqlen=len(resultset),
                      default_size=self.batch_size)
        return {
            'batch':batch,
            'filter_text':request.params.get('filter_text'),
            'reverse':request.params.get('reverse', 'false')
            }

    def query(self):
        request = self.request
        context = self.context
        q = find_index(context, 'yss', 'oid').any(context.recording_ids)
        q = q & find_index(context, 'system', 'content_type').eq('Recording')
        q = q & find_index(context, 'system', 'allowed').allows(
            request, 'yss.indexed')
        filter_text = request.params.get('filter_text')
        if filter_text:
            terms = generate_text_filter_terms(filter_text)
            text = find_index(context, 'yss', 'text')
            for term in terms:
                if text.check_query(term):
                    q = q & text.eq(term)
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
        num_likes = find_index(context, 'yss', 'num_likes')
        genre = find_index(context, 'yss', 'genre')
        created = find_index(context, 'yss', 'created')
        sorting = {
            'created':(created, num_likes, title, performer, genre),
            'title':(title, performer, num_likes, genre, created),
            'performer':(performer, title, num_likes, genre, created),
            'genre':(genre, performer, title, num_likes, created),
            'likes':(num_likes, performer, title, genre, created),
            }
        indexes = sorting.get(token, sorting[self.default_sort])
        for idx in indexes[1:]:
            rs = rs.sort(idx)
        first = indexes[0]
        rs = rs.sort(first, reverse=reverse)
        return rs

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

        query = [
            ('sorting', token), ('reverse', reverse)
        ]
        filter_text = request.params.get('filter_text')

        if filter_text:
            query.append(
                ('filter_text', filter_text)
                )

        url = request.resource_url(context, query=query)

        return '<a href="%s">%s <i class="%s"> </i></a>' % (
            url,
            title,
            icon,
            )

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

def get_recording_tempdir(request, recording_id):
    postproc_dir = request.registry.settings['yss.postproc_dir']
    return os.path.abspath(os.path.join(postproc_dir, recording_id))

def get_retime_tempdir(request, song_id):
    retime_dir = request.registry.settings['yss.retime_dir']
    return os.path.abspath(os.path.join(retime_dir, song_id))

@colander.deferred
def audio_validator(node, kw):
    def _audio_validator(node, value):
        mimetype = value['mimetype']
        if not mimetype.startswith('audio/'):
            raise colander.Invalid(
                node,
                f'Audio file must be an audio file (not {mimetype})'
            )
    return _audio_validator

class SongEditSchema(Schema):
    """ Property schema for song upload/edit
    """
    title = colander.SchemaNode(
        colander.String(),
        title='Song Title',
        validator=colander.Length(max=100),
    )

    artist = colander.SchemaNode(
        colander.String(),
        title='Artist Name',
        validator=colander.Length(max=100),
    )

    genre = colander.SchemaNode(
        colander.String(),
        title='Song Genre',
        widget=deform.widget.SelectWidget(values=genre_choices),
    )
    language = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.Select2Widget(values=language_choices),
    )
    lyrics = colander.SchemaNode(
        colander.String(),
        validator=colander.Length(max=20000),
        widget=deform.widget.TextAreaWidget(style="height: 200px;"),
    )
    year = colander.SchemaNode(
        colander.Int(),
        validator=colander.Range(0, 3000)
    )

class SongUploadSchema(SongEditSchema):
    audio_file = FileNode(
        title='Backing Track (audio file like mp3/aac/wav)',
        validator=audio_validator,
    )

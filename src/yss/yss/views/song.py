import colander
import deform.widget
import slug

from pyramid.httpexceptions import HTTPBadRequest
from pyramid.view import view_config
from pyramid.settings import asbool
from pyramid.httpexceptions import HTTPFound

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


@mgmt_view(context=ISongs, name='preview')
def preview_songs(context, request):
    return HTTPFound(location=request.resource_url(context))

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

    @view_config(
        context=ISongs,
        renderer='templates/songs.pt'
    )
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

class SongView(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @view_config(
        context=ISong,
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
            }

    @view_config(
        context=ISong,
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

@view_config(
    context=ISong,
    name='mp3',
    permission='view',
)
def stream_mp3(context, request):
    return context.get_response(request=request)



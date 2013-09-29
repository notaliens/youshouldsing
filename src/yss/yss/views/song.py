from pyramid.view import view_config
from pyramid.settings import asbool

from substanced.util import (
    Batch,
    find_index,
    )

from substanced.folder.views import generate_text_filter_terms

from yss.interfaces import ISongs

class SongsView(object):
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
            resultset = self.sort_by(resultset, 'artist', False)
        return resultset

    def sort_by(self, rs, token, reverse):
        context = self.context
        title = find_index(context, 'yss', 'title')
        artist = find_index(context, 'yss', 'artist')
        likes = find_index(context, 'yss', 'likes')
        genre = find_index(context, 'yss', 'genre')
        created = find_index(context, 'yss', 'created')
        sorting = {
            'date':(created, likes, title, artist, genre),
            'title':(title, artist, likes, genre, created),
            'artist':(artist, title, likes, genre, created),
            'genre':(genre, artist, title, likes, created),
            'likes':(likes, artist, title, genre, created),
            }
        indexes = sorting.get(token, sorting['artist'])
        first = indexes[0]
        rs = rs.sort(first, reverse=reverse)
        for idx in indexes[1:]:
            rs = rs.sort(idx)
        return rs

    @view_config(context=ISongs, renderer='templates/songs.pt')
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

    def sort_url(self, token):
        request = self.request
        context = self.context
        reverse = request.params.get('reverse', 'false')
        reverse = asbool(reverse)
        reverse = reverse and 'false' or 'true'
        return request.resource_url(
            context, query=(
                ('sorting', token), ('reverse', reverse)
                )
            )

    def sort_icon(self, token):
        request = self.request
        sorting = request.params.get('sorting')
        reverse = request.params.get('reverse', 'false')
        reverse = asbool(reverse)
        icon = ''
        if sorting == token:
            if reverse:
                icon = 'glyphicon glyphicon-chevron-up'
            else:
                icon = 'glyphicon glyphicon-chevron-down'
        return icon

def sort_by_indexes(resultset, indexes, reverse=False):
    first = indexes[0]
    resultset = resultset.sort(first, reverse=reverse)
    return resultset
    for index in indexes[1:]:
        resultset = resultset.sort(index)
    return resultset

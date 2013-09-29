# Retail profile views
import colander
import deform

from pyramid.httpexceptions import HTTPBadRequest
from pyramid.settings import asbool
from pyramid.view import view_config
from substanced.folder.views import generate_text_filter_terms
from substanced.util import (
    Batch,
    find_index,
    )

from ..interfaces import IPerformer
from ..interfaces import IPerformers
from ..resources import PerformerProfileSchema

def recent_recordings(context, request, limit=10):
    q = find_index(context, 'system', 'content_type').eq('Recording')
    q = q & find_index(context, 'system', 'allowed').allows(
        request, 'view')
    created = find_index(context, 'yss', 'created')
    resultset = q.execute()
    return resultset.sort(created, reverse=True, limit=limit)

@view_config(
    context=IPerformer,
    renderer='templates/profile.pt',
)
def profile_view(context, request):
    return {
        'username': context.__name__,
        'title': getattr(context, 'title', ''),
        'email': getattr(context, 'email', ''),
        'photo_url': getattr(context, 'photo_url', ''),
        'age': getattr(context, 'age', colander.null),
        'sex': getattr(context, 'sex', None),
        'genre': getattr(context, 'genre', None),
        'form': None,
        'recent_recordings': recent_recordings(context, request),
        'likes': context.likes,
    }
    form = deform.Form(PerformerProfileSchema(), buttons=('Save',))

@view_config(
    context=IPerformer,
    name='like',
    renderer='json',
)
def like_profile(context, request):
    performer = request.user.performer
    if performer in context.liked_by:
        raise HTTPBadRequest("Already")
    context.liked_by.connect([performer])
    return {'ok': True,
            'likes': context.likes,
            }

@view_config(
    context=IPerformer,
    renderer='templates/profile.pt',
    name='edit.html',
#    permission='edit', XXX
)
def profile_edit_form(context, request):
    schema = PerformerProfileSchema().bind(request=request, context=context)
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
            context.email = appstruct['email']
            context.photo_url = appstruct['photo_url']
            context.age = appstruct['age']
            context.sex = appstruct['sex']
            context.genre = appstruct['genre']
    else:
        appstruct = {
            'csrf_token': request.session.get_csrf_token(),
            'username': context.__name__,
            'title': getattr(context, 'title', ''),
            'email': getattr(context, 'email', ''),
            'photo_url': getattr(context, 'photo_url', ''),
            'age': getattr(context, 'age', colander.null),
            'sex': getattr(context, 'sex', None),
            'genre': getattr(context, 'genre', None),
        }
    if rendered is None:
        rendered = form.render(appstruct, readonly=False)
    return {
        'form': rendered,
    }


class PerformersView(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def query(self):
        request = self.request
        context = self.context
        q = find_index(context, 'system', 'content_type').eq('Performer')
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
            resultset = self.sort_by(resultset, 'date', False)
        return resultset

    def sort_by(self, rs, token, reverse):
        context = self.context
        title = find_index(context, 'yss', 'title')
        likes = find_index(context, 'yss', 'likes')
        genre = find_index(context, 'yss', 'genre')
        created = find_index(context, 'yss', 'created')
        sorting = {
            #'date':(created, likes, title, genre),
            'date':(created,),
            'title':(title, likes, genre, created),
            'genre':(genre, title, likes, created),
            'likes':(likes, title, genre, created),
            }
        indexes = sorting.get(token, sorting['date'])
        for idx in indexes[1:]:
            rs = rs.sort(idx)
        first = indexes[0]
        rs = rs.sort(first, reverse=reverse)
        return rs

    @view_config(context=IPerformers, renderer='templates/performers.pt')
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
        if sorting == token or (not sorting and token == 'artist'):
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


from pyramid.response import FileResponse
from pyramid.view import (
    view_config,
    view_defaults,
    )
from pyramid.decorator import reify

from pyramid.settings import asbool
from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPFound,
    )

from substanced.event import ObjectModified
from substanced.interfaces import IRoot

from substanced.util import (
    find_index,
    Batch,
    )

from substanced.folder.views import generate_text_filter_terms
from substanced.workflow import get_workflow

from yss.interfaces import IRecording

@view_defaults(context=IRecording)
class RecordingView(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @reify
    def page_title(self):
        recording = self.context
        return f'{recording.title} performed by {recording.performer.__name__}'

    @reify
    def has_edit_permission(self):
        recording = self.context
        has_edit_permission = self.request.has_permission('yss.edit', recording)
        return has_edit_permission

    def tabs(self):
        state = self.request.view_name
        recording = self.context
        tabs = []
        if self.has_edit_permission:
            tabs.append(
                {'title':'View',
                 'id':'button-view',
                 'url':self.request.resource_url(recording),
                 'class':(state == '') and 'active' or '',
                 'enabled':True,
                 })
            tabs.append(
                {'title':'Edit',
                 'id':'button-edit',
                 'url':self.request.resource_url(recording, '@@remixpage'),
                 'class':(state == 'remixpage') and 'active' or '',
                 'enabled':True # XXX if we are already remixing, disable
                 })
        return tabs

    @view_config(
        context=IRecording,
        renderer='templates/recording.pt',
        permission='view',
    )
    def view(self):
        recording = self.context
        request = self.request
        return {
            'title':recording.title,
            'performer':recording.performer,
            'num_likes':recording.num_likes,
            'liked_by': recording.liked_by,
            'stream_url': request.resource_url(recording, '@@movie'),
            'mixed': recording.mixed,
            'has_edit_permission':int(self.has_edit_permission),
            }

    @view_config(
        context=IRecording,
        name='dry',
        renderer='templates/recording.pt',
        permission='yss.edit',
    )
    def dry(self):
        # for debugging: /dry, never intended to be exposed in the UI
        vars = self.view()
        vars['stream_url'] = self.request.resource_url(
            self.context, '@@drymovie')
        return vars

    @view_config(
        name='remixpage',
        renderer='templates/remix.pt',
        permission='yss.edit',
        )
    def remixpage(self):
        recording = self.context
        request = self.request
        visibility_wf = get_workflow(request, 'Visibility', 'Recording')
        return {
            'remix_handler': request.resource_url(recording, '@@remix'),
            'rej_handler': request.resource_url(recording, '@@remixreject'),
            'acc_handler': request.resource_url(recording, '@@remixaccept'),
            'voladjust': recording.voladjust,
            'effects':recording.effects,
            'stream_url':request.resource_url(recording, '@@remixmovie'),
            'progress_url':request.resource_url(recording,'@@remixprogress'),
            'page_title':f'Remixing {self.page_title}',
            'enqeued':recording.enqueued,
            # ismixed false means fresh from song record, and not a remix
            'ismixed':bool(recording.mixed),
            'visibility_state':visibility_wf.state_of(recording),
            'visibility_states':visibility_states,
        }

    @view_config(
        name='remixprogress',
        renderer='json',
        permission='view',
    )
    def remixprogress(self):
        return self.context.get_mixprogress(self.request)

    @view_config(
        name='remix',
        permission='yss.edit',
        renderer='string',
    )
    def remix(self):
        request = self.request
        recording = self.context
        needs_remix = False

        known_effects = ('effect-chorus', 'effect-reverb') # XXX centralize
        desired_effects = tuple([
            x for x in request.params.getall('effects') if x in known_effects
        ])

        if set(desired_effects) != set(recording.effects):
            needs_remix = True
            recording.effects = tuple(desired_effects)

        try:
            voladjust = request.params.get('voladjust', 0)
            voladjust = float(voladjust)
            if -1 > voladjust > 1:
                raise ValueError
        except (TypeError, ValueError):
            request.session.flash('Bad voladjust', 'danger')
            return request.resource_url(self.context, 'remix')

        if str(voladjust) != str(recording.voladjust):
            needs_remix = True
            recording.voladjust = voladjust

        show_camera = request.params.get('show-camera', 'true')
        show_camera = show_camera == 'true' and True or False

        if bool(show_camera) != bool(recording.show_camera):
            needs_remix = True
            recording.show_camera = show_camera

        try:
            latency = request.params.get('latency', 0)
            latency = float(latency)
            if 0 > latency > 2:
                raise ValueError
        except (TypeError, ValueError):
            request.session.flash('Bad latency', 'danger')
            return request.resource_url(self.context, 'remix')

        if latency != recording.latency:
            needs_remix = True
            recording.latency = latency

        request.response.set_cookie('latency', str(latency))

        if needs_remix:
            recording.enqueue(request)
            event = ObjectModified(recording)
            self.request.registry.subscribers((event, recording), None)
            progress_url = request.resource_url(self.context, '@@remixprogress')
            return progress_url

        return ''

    @view_config(
        name='remixreject',
        permission='yss.edit',
        renderer='string',
    )
    def remix_reject(self):
        request = self.request
        recording = self.context
        song = recording.song
        del recording.__parent__[recording.__name__]
        return request.resource_url(song, '@@record')

    @view_config(
        name='remixaccept',
        permission='yss.edit',
        renderer='string',
    )
    def remix_accept(self):
        request = self.request
        recording = self.context
        description = request.params.get('description', '')
        description = description[:2000]
        recording.description = description
        visibility = request.params.get('visibility', 'Private')
        if not visibility in visibility_states:
            visibility = 'Private'
        visibility_wf = get_workflow(request, 'Visibility', 'Recording')
        visibility_wf.transition_to_state(recording, request, visibility)
        recording.set_mixed()
        event = ObjectModified(recording)
        self.request.registry.subscribers((event, recording), None)
        request.session.flash('Recording changes accepted', 'info')
        return request.resource_url(recording)

    @view_config(
        name='like',
        renderer='json',
        permission='yss.like',
    )
    def like(self):
        request = self.request
        recording = self.context
        performer = request.performer
        if not performer in recording.liked_by:
            recording.liked_by.connect([performer])
            event = ObjectModified(recording)
            self.request.registry.subscribers((event, recording), None)

        return {'ok': True,
                'num_likes': recording.num_likes,
                'can_like':request.layout_manager.layout.can_like(recording),
        }

    @view_config(
        name='unlike',
        renderer='json',
        permission='yss.like',
    )
    def unlike(self):
        request = self.request
        recording = self.context
        performer = request.performer
        if performer in recording.liked_by:
            recording.liked_by.disconnect([performer])
            event = ObjectModified(recording)
            self.request.registry.subscribers((event, recording), None)

        return {'ok': True,
                'num_likes': recording.num_likes,
                'can_like':request.layout_manager.layout.can_like(recording),
        }

    def _stream_file(self, filename, content_type):
        request = self.request
        if request.range:
            if request.range.start == 0 and request.range.end == None:
                # it's ff or chrome seeing if we support range requests, return
                # a smaller amount because initial requests from those browsers
                # drop the connection and throw any data we send anyway.
                request.range = 'bytes=0-4096'

        response = FileResponse(
            filename,
            request=self.request,
            content_type=content_type,
            cache_max_age=0,
        )
        response.accept_ranges = 'bytes'
        return response

    def _stream_blob(self, blob, content_type):
        if not blob:
            return HTTPBadRequest('Video still processing')
        return self._stream_file(blob.committed(), content_type)

    @view_config(
        name='movie',
        permission='view'
    )
    def stream_mixed(self):
        recording = self.context
        return self._stream_blob(recording.mixed_blob, 'video/webm')

    @view_config(
        name='remixmovie',
        permission='yss.edit'
    )
    def stream_remixing(self):
        recording = self.context
        blob = recording.remixing_blob
        if blob is None:
            blob = recording.mixed_blob
        return self._stream_blob(blob, 'video/webm')

    @view_config(
        name='drymovie',
        permission='yss.edit'
    )
    def stream_dry(self):
        # never expose this publicly
        recording = self.context
        return self._stream_blob(recording.dry_blob, 'video/webm')

    @view_config(
        name='delete',
        permission='yss.edit'
    )
    def delete(self):
        recordings = self.context.__parent__
        name = self.context.__name__
        del recordings[name]
        performer = recordings.__parent__
        self.request.session.flash('Recording deleted', 'danger')
        return HTTPFound(self.request.resource_url(performer, '@@recordings'))

class GlobalRecordingsView(object):
    default_sort = 'created'
    default_sort_reversed = True
    batch_size = 20
    page_title = 'Recordings'
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def get_sort_params(self):
        request = self.request
        sorting = request.params.get('sorting', None)
        if sorting is None:
            sorting = self.default_sort
            reverse = self.default_sort_reversed
        else:
            reverse = asbool(request.params.get('reverse'))
        return sorting, reverse

    def query(self):
        request = self.request
        context = self.context
        q = find_index(context, 'system', 'content_type').eq('Recording')
        q = q & find_index(context, 'system', 'allowed').allows(
            ['system.Everyone'], 'yss.indexed')
        q = q & find_index(context, 'yss', 'mixed').eq(True)
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
        sorting, reverse = self.get_sort_params()
        resultset = self.sort_by(resultset, sorting, reverse)
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

    @view_config(
        context=IRoot,
        name='recordings',
        renderer='templates/recordings.pt'
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
        sorting, reverse = self.get_sort_params()
        if sorting == token:
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

        url = request.resource_url(context, '@@recordings', query=query)

        return '<a href="%s">%s <i class="%s"> </i></a>' % (
            url,
            title,
            icon
            )

visibility_states = (
    'Public',
    'Private',
    'Authenticated Only',
    ) # XXX probably should derive these from workflow

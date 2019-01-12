import colander
import deform
import time

from pyramid.response import FileResponse
from pyramid.view import (
    view_config,
    view_defaults,
    )
from pyramid.settings import asbool
from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPFound,
    )

from substanced.interfaces import IRoot

from substanced.util import (
    find_index,
    Batch,
    )

from substanced.folder.views import generate_text_filter_terms
from substanced.schema import Schema
from substanced.workflow import get_workflow

from yss.utils import get_redis, decode_redis_hash

from yss.interfaces import IRecording

from pyramid.decorator import reify

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
    def is_processed(self):
        recording = self.context
        return bool(recording.mixed_blob and not recording.remixing)

    @reify
    def has_edit_permission(self):
        recording = self.context
        has_edit_permission = self.request.has_permission('yss.edit', recording)
        return has_edit_permission

    def tabs(self):
        state = self.request.view_name
        recording = self.context
        processed = self.is_processed
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
                 'url':self.request.resource_url(recording, '@@edit'),
                 'class':(state == 'edit') and 'active' or '',
                 'enabled':True,
                 })
            tabs.append(
                {'title':'Remix',
                 'id':'button-remix',
                 'url':self.request.resource_url(recording, '@@remix'),
                 'class':(state == 'remix') and 'active' or '',
                 'enabled':processed,
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
        # XXX compute other_recordings more efficiently
        other_recordings = [
            other_recording for other_recording in
            recording.song.recordings if
            other_recording is not recording and
            request.has_permission('yss.indexed', other_recording)
            ]
        return {
            'title':recording.title,
            'performer':recording.performer,
            'num_likes':recording.num_likes,
            'liked_by': recording.liked_by,
            'other_recordings':other_recordings,
            'video_url': request.resource_url(recording, 'movie'),
            'processed': int(self.is_processed),
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
        vars['video_url'] = self.request.resource_url(self.context, 'drymovie')
        return vars

    @view_config(
        name='edit',
        renderer='templates/edit.pt',
        permission='yss.edit',
    )
    def edit(self):
        recording = self.context
        request = self.request
        visibility_wf = get_workflow(request, 'Visibility', 'Recording')
        schema = EditRecordingSchema().bind(request=request, context=recording)
        form = deform.Form(schema, buttons=('Save',))
        # XXX wtf if I take this out, my visibility choices disappear
        # on successful save until a process restart
        form['visibility'].widget=deform.widget.RadioChoiceWidget(
            values=zip(visibility_states, visibility_states)
        )
        rendered = None
        if 'Save' in request.POST:
            controls = request.POST.items()
            try:
                appstruct = form.validate(controls)
            except deform.ValidationFailure as e:
                rendered = e.render()
            else:
                recording.description = appstruct['description']
                visibility_wf.transition_to_state(
                    recording, request, appstruct['visibility']
                )
                # reindex visibility state
                index = find_index(recording, 'yss', 'visibility_state')
                index.reindex_doc(recording.__oid__, appstruct['visibility'])
                if appstruct['allow_likes']:
                    # XXXX
                    pass
                request.session.flash('Recording edited', 'info')
                return HTTPFound(request.resource_url(recording, 'edit'))
        else:
            appstruct = {
                'csrf_token': request.session.get_csrf_token(),
                'description': recording.description,
                'visibility':visibility_wf.state_of(recording),
                'allow_likes':False,
            }
        if rendered is None:
            rendered = form.render(appstruct, readonly=False)
        return {
            'form':rendered,
            'page_title': f'Editing {self.page_title}'
            }

    @view_config(
        name='mixprogress',
        renderer='json',
        permission='view',
    )
    def mixprogress(self):
        redis = get_redis(self.request)
        recording = self.context
        progress = decode_redis_hash(
            redis.hgetall(f'mixprogress-{self.context.__oid__}')
            )
        progress['done'] = (
            (recording.mixed_blob and not recording.remixing) and 1 or 0
            )
        return progress

    @view_config(
        name='remix',
        renderer='templates/remix.pt',
        permission='yss.edit',
        )
    def remix(self):
        # XXX check if dry blob is still around
        return {
            'submit_handler': self.request.resource_url(
                self.context, 'finish_remix'),
            'musicvolume': self.context.musicvolume,
            'effects':self.context.effects,
            'stream_url':self.request.resource_url(
                self.context, 'movie'),
            'already':self.context.remixing,
            'page_title':f'Remixing {self.page_title}'
            }

    @view_config(
        name='finish_remix',
        permission='yss.edit',
        renderer='string',
    )
    def finish_remix(self):
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

        # need to validate musicvolume and return an error

        try:
            musicvolume = request.params.get('musicvolume', 0.5)
            musicvolume = float(musicvolume)
            if 0 > musicvolume > 1:
                raise ValueError
        except (TypeError, ValueError):
            request.session.flash('Bad musicvolume', 'danger')
            return request.resource_url(self.context, 'remix')

        if str(musicvolume) != str(recording.musicvolume):
            needs_remix = True
            recording.musicvolume = musicvolume

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

        if needs_remix:
            recording.remixing = True
            redis = get_redis(request)
            redis.rpush(
                "yss.new-recordings", f'{recording.__oid__}|{time.time()}')

        return request.resource_url(self.context)

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
        return {'ok': True,
                'num_likes': recording.num_likes,
                'can_like':request.layout_manager.layout.can_like(recording),
        }

    @view_config(
        name='movie',
        permission='view'
    )
    def stream_mixed(self):
        recording = self.context
        if recording.mixed_blob:
            return FileResponse(
                recording.mixed_blob.committed(),
                content_type='video/webm'
            )
        return HTTPBadRequest('Video still processing')

    @view_config(
        name='drymovie',
        permission='yss.edit'
    )
    def stream_dry(self):
        recording = self.context
        if recording.dry_blob:
            return FileResponse(
                recording.dry_blob.committed(),
                content_type='video/webm'
            )
        return HTTPBadRequest('Video still processing')

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

@colander.deferred
def visibility_widget(node, kw):
    # XXX wtf if I just use RadioChoiceWidget directly without a deferral,
    # my visibility choices disappear on successful save until a process restart
    deform.widget.RadioChoiceWidget(
        values=zip(visibility_states, visibility_states)
    )

class EditRecordingSchema(Schema):
    """ Property schema to create a Performer.
    """
    description = colander.SchemaNode(
        colander.String(),
        title='Description',
        validator=colander.Length(max=2000),
        widget=deform.widget.TextAreaWidget(rows=6),
        missing=colander.null,
    )
    visibility = colander.SchemaNode(
        colander.String(),
        title='Visibility',
        widget=visibility_widget,
    )

    allow_likes = colander.SchemaNode(
        colander.Bool(),
        title='Allow Likes',
    )

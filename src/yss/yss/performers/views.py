# Retail profile views
import colander
import deform
import io
import PIL.Image

from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.settings import asbool
from pyramid.view import (
    view_config,
    view_defaults,
    )
from substanced.folder.views import generate_text_filter_terms
from substanced.util import (
    Batch,
    find_index,
    )
from substanced.schema import Schema
from substanced.workflow import get_workflow

from yss.interfaces import (
    IPerformer,
    IPerformers,
    IPerformerPhoto,
    )

from yss.performers import PerformerProfileSchema

from yss.utils import get_photodata

@view_defaults(context=IPerformer)
class PerformerView(object):
    batch_size = 20
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @reify
    def has_edit_permission(self):
        performer = self.context
        return self.request.has_permission('yss.edit', performer)

    @reify
    def has_view_permission(self):
        performer = self.context
        return self.request.has_permission('view', performer)

    def tabs(self):
        state = self.request.view_name
        performer = self.context
        tabs = []
        if self.has_view_permission:
            tabs.append(
                {'title':'View',
                 'id':'button-view',
                 'url':self.request.resource_url(performer),
                 'class':state == '' and 'active' or '',
                 'enabled':True,
                 })
            tabs.append(
                {'title':'Recordings',
                 'id':'button-recordings',
                 'url':self.request.resource_url(performer, '@@recordings'),
                 'class':state == 'recordings' and 'active' or '',
                 'enabled':True,
                 })
            if performer.divulge_recording_likes:
                tabs.append(
                    {'title':'Recordings Liked',
                     'id':'button-recordingsliked',
                     'url':self.request.resource_url(
                         performer, '@@recordingsliked'),
                     'class':state == 'recordingsliked' and 'active' or '',
                     'enabled':True,
                    })
            if performer.divulge_song_likes:
                tabs.append(
                    {'title':'Songs Liked',
                     'id':'button-songsliked',
                     'url':self.request.resource_url(performer, '@@songsliked'),
                     'class':state == 'songsliked' and 'active' or '',
                     'enabled':True,
                    })
            if performer.divulge_performer_likes:
                tabs.append(
                    {'title':'Performers Liked',
                     'id':'button-performersliked',
                     'url':self.request.resource_url(
                         performer, '@@performersliked'),
                     'class':state == 'performersliked' and 'active' or '',
                     'enabled':True,
                    })

        if self.has_edit_permission:
            tabs.append(
                {'title':'Edit',
                 'id':'button-edit',
                 'url':self.request.resource_url(performer, '@@edit'),
                 'class':state=='edit' and 'active' or '',
                 'enabled':True,
                 })
            tabs.append(
                {'title':'Privacy',
                 'id':'button-privacy',
                 'url':self.request.resource_url(performer, '@@privacy'),
                 'class':state=='privacy' and 'active' or '',
                 'enabled':True,
                 })
        return tabs

    @view_config(
        renderer='templates/profile.pt',
        permission='view',
    )
    def view(self):
        context = self.context
        request = self.request
        return {
            'username': context.__name__,
            'title': getattr(context, 'title', ''),
            'name': context.__name__,
            'email': getattr(context, 'email', ''),
            'birthdate': getattr(context, 'birthdate', colander.null),
            'location': getattr(context, 'location', colander.null),
            'age':getattr(context, 'age', 0),
            'sex': getattr(context, 'sex', None),
            'genre': getattr(context, 'genre', None),
            'tzname': getattr(context, 'tzname', 'UTC'),
            'num_likes': context.num_likes,
            'can_edit': request.performer is context,
            'divulge_recording_likes': context.divulge_recording_likes,
            'divulge_performer_likes': context.divulge_performer_likes,
            'divulge_song_likes': context.divulge_song_likes,
            'divulge_age': context.divulge_age,
            'divulge_realname':context.divulge_realname,
            'divulge_location':context.divulge_location,
            'divulge_genre':context.divulge_genre,
            'divulge_sex':context.divulge_sex,
        }

    def sfilter(self, resources, perm='yss.indexed'):
        allowed = []
        for resource in resources:
            if self.request.has_permission(perm, resource):
                allowed.append(resource)
        return allowed

    @view_config(
        name='like',
        renderer='json',
        permission='yss.like',
    )
    def like(self):
        request = self.request
        context = self.context
        performer = request.performer
        if performer in context.liked_by:
            raise HTTPBadRequest("Already")
        context.liked_by.connect([performer])
        find_index(self.context, 'yss', 'num_likes').reindex_doc(
            context.__oid__, len(context.liked_by))
        return {'ok': True,
                'num_likes': context.num_likes,
                'can_like':request.layout_manager.layout.can_like(performer),
                }

    @view_config(
        name='unlike',
        renderer='json',
        permission='yss.like',
    )
    def unlike(self):
        request = self.request
        context = self.context
        performer = request.performer
        if performer in context.liked_by:
            context.liked_by.disconnect([performer])
        find_index(self.context, 'yss', 'num_likes').reindex_doc(
            context.__oid__, len(context.liked_by))
        return {'ok': True,
                'num_likes': context.num_likes,
                'can_like':request.layout_manager.layout.can_like(performer),
                }

    def sort_tag(self, token, title):
        request = self.request
        context = self.context
        reverse = request.params.get('reverse', 'false')
        reverse = asbool(reverse)
        sorting = request.params.get('sorting')
        view_name = request.view_name
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

        url = request.resource_url(context, f'@@{view_name}', query=query)

        return '<a href="%s">%s <i class="%s"> </i></a>' % (
            url,
            title,
            icon
            )


@view_defaults(context=IPerformer)
class PerformerRecordingsView(PerformerView):
    default_sort = 'created'
    def sort_by(self, rs, token, reverse):
        context = self.context
        title = find_index(context, 'yss', 'title')
        performer = find_index(context, 'yss', 'performer')
        num_likes = find_index(context, 'yss', 'num_likes')
        genre = find_index(context, 'yss', 'genre')
        created = find_index(context, 'yss', 'created')
        visib = find_index(context, 'yss', 'visibility_state')
        sorting = {
            'created':(created, num_likes, title, performer, genre, visib),
            'title':(title, performer, num_likes, genre, created, visib),
            'performer':(performer, title, num_likes, genre, created, visib),
            'genre':(genre, performer, title, num_likes, created, visib),
            'likes':(num_likes, performer, title, genre, created, visib),
            'visibility':(visib, created, num_likes, title, performer, genre)
            }
        indexes = sorting.get(token, sorting[self.default_sort])
        for idx in indexes[1:]:
            rs = rs.sort(idx)
        first = indexes[0]
        rs = rs.sort(first, reverse=reverse)
        return rs

    def query(self):
        request = self.request
        context = self.context
        q = find_index(context, 'system', 'content_type').eq('Recording')
        q = q & find_index(context, 'system', 'path').eq(
            request.resource_path(context, 'recordings')
        )
        permission = (
            (context == request.performer and 'view' or 'yss.indexed')
            )
        q = q & find_index(context, 'system', 'allowed').allows(
            request, permission)
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

    @view_config(
        renderer='templates/profile_recordings.pt',
        name='recordings',
        permission='view',
    )
    def __call__(self):
        vals = self.view()
        request = self.request
        resultset = self.query()
        batch = Batch(resultset, self.request, seqlen=len(resultset),
                      default_size=self.batch_size)
        vals.update({
            'batch':batch,
            'filter_text':request.params.get('filter_text'),
            'reverse':request.params.get('reverse', 'false')
            })
        return vals

    def visibility_state(self, recording):
        wf = get_workflow(self.request, 'Visibility', 'Recording')
        return wf.state_of(recording)


@view_defaults(context=IPerformer)
class PerformerSongsLikedView(PerformerView):
    default_sort='artist'

    def sort_by(self, rs, token, reverse):
        context = self.context
        title = find_index(context, 'yss', 'title')
        num_likes = find_index(context, 'yss', 'num_likes')
        artist = find_index(context, 'yss', 'artist')
        num_recordings = find_index(context, 'yss', 'num_recordings')
        duration = find_index(context, 'yss', 'duration')
        num_likes = find_index(context, 'yss', 'num_likes')
        genre = find_index(context, 'yss', 'genre')
        sorting = {
            'title':
            (title, artist, num_recordings, num_likes, genre),
            'artist':
            (artist, title, num_recordings, num_likes, genre),
            'genre':
            (genre, artist, title, num_recordings, num_likes),
            'num_likes':
            (num_likes, artist, title, num_recordings, genre),
            'num_recordings':
            (num_recordings, artist, title, num_likes, genre),
            'duration':
            (duration, artist, title, genre, num_likes, num_recordings),
            }
        indexes = sorting.get(token, sorting[self.default_sort])
        for idx in indexes[1:]:
            rs = rs.sort(idx)
        first = indexes[0]
        rs = rs.sort(first, reverse=reverse)
        return rs

    def query(self):
        request = self.request
        context = self.context
        q = find_index(context, 'yss', 'oid').any(context.likes_songids)
        q = q & find_index(context, 'system', 'content_type').eq('Song')
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


    @view_config(
        renderer='templates/profile_songsliked.pt',
        name='songsliked',
        permission='view',
    )
    def __call__(self):
        vals = self.view()
        if vals['divulge_song_likes']:
            resultset = self.query()
        else:
            resultset = []
        request = self.request
        batch = Batch(resultset, request, seqlen=len(resultset),
                      default_size=self.batch_size)
        vals.update({
            'batch':batch,
            'filter_text':request.params.get('filter_text'),
            'reverse':request.params.get('reverse', 'false')
            })
        return vals

@view_defaults(context=IPerformer)
class PerformerPerformersLikedView(PerformerView):
    default_sort = 'name'

    def sort_by(self, rs, token, reverse):
        context = self.context
        name = find_index(context, 'system', 'name')
        num_likes = find_index(context, 'yss', 'num_likes')
        num_recordings = find_index(context, 'yss', 'num_likes')
        created = find_index(context, 'yss', 'created')
        sorting = {
            'created':(created, num_likes, num_recordings, name),
            'name':(name, num_likes, created, num_recordings),
            'likes':(num_likes, name, num_recordings, created),
            'recordings':(num_recordings, num_likes, name, created),
            }
        indexes = sorting.get(token, sorting[self.default_sort])
        for idx in indexes[1:]:
            rs = rs.sort(idx)
        first = indexes[0]
        rs = rs.sort(first, reverse=reverse)
        return rs

    def query(self):
        request = self.request
        context = self.context
        q = find_index(context, 'yss', 'oid').any(context.likes_performerids)
        q = q & find_index(context, 'system', 'content_type').eq('Performer')
        q = q & find_index(context, 'system', 'allowed').allows(
            request, 'view')
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

    @view_config(
        renderer='templates/profile_performersliked.pt',
        name='performersliked',
        permission='view',
    )
    def __call__(self):
        vals = self.view()
        if vals['divulge_performer_likes']:
            resultset = self.query()
        else:
            resultset = []
        request = self.request
        batch = Batch(resultset, request, seqlen=len(resultset),
                      default_size=self.batch_size)
        vals.update({
            'batch':batch,
            'filter_text':request.params.get('filter_text'),
            'reverse':request.params.get('reverse', 'false')
            })
        return vals

@view_defaults(context=IPerformer)
class PerformerRecordingsLikedView(PerformerView):
    default_sort='created'

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

    def query(self):
        request = self.request
        context = self.context
        q = find_index(context, 'yss', 'oid').any(context.likes_recordingids)
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

    @view_config(
        renderer='templates/profile_recordingsliked.pt',
        name='recordingsliked',
        permission='view',
    )
    def __call__(self):
        vals = self.view()
        if vals['divulge_recording_likes']:
            resultset = self.query()
        else:
            resultset = []
        request = self.request
        batch = Batch(resultset, request, seqlen=len(resultset),
                      default_size=self.batch_size)
        vals.update({
            'batch':batch,
            'filter_text':request.params.get('filter_text'),
            'reverse':request.params.get('reverse', 'false')
            })
        return vals

@view_defaults(context=IPerformer)
class PerformerEditView(PerformerView):

    @view_config(
        renderer='templates/profile_edit.pt',
        name='edit',
        permission='yss.edit',
    )
    def __call__(self):
        vars = self.view()
        context = self.context
        request = self.request
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
                photo = context['photo']
                photo_thumbnail = context['photo_thumbnail']
                phdata = appstruct['photo']
                fp = phdata.get('fp')
                if fp is not None:
                    for photo_object, photosize in (
                            (photo, (320, 320)),
                            (photo_thumbnail, (40, 40)),
                    ):
                        fp.seek(0)
                        pil_image = PIL.Image.open(fp)
                        if pil_image.size[0] != photosize[0]: # width
                            pil_image.thumbnail(photosize, PIL.Image.ANTIALIAS)
                        buffer = io.BytesIO()
                        pil_image.save(buffer, 'png')
                        buffer.seek(0)
                        photo_object.upload(buffer)
                        photo_object.mimetype = 'image/png'
                context.birthdate = appstruct['birthdate']
                context.sex = appstruct['sex']
                context.genre = appstruct['genre']
                context.tzname = appstruct['tzname']
                context.location = appstruct['location']
                request.session.flash('Profile edited', 'info')
        else:
            photodata = get_photodata(context, request)
            appstruct = {
                'csrf_token': request.session.get_csrf_token(),
                'username': context.__name__,
                'title': getattr(context, 'title', ''),
                'photo': photodata,
                'email': getattr(context, 'email', ''),
                'birthdate': getattr(context, 'birthdate', colander.null),
                'sex': getattr(context, 'sex', None),
                'genre': getattr(context, 'genre', None),
                'tzname':getattr(context, 'tzname', None),
                'location':getattr(context, 'location', ''),
            }
        if rendered is None:
            rendered = form.render(appstruct, readonly=False)
        vars['form'] = rendered
        return vars

@view_defaults(context=IPerformer)
class PerformerPrivacyView(PerformerView):

    @view_config(
        renderer='templates/profile_privacy.pt',
        name='privacy',
        permission='yss.edit',
    )
    def __call__(self):
        vars = self.view()
        context = self.context
        request = self.request
        schema = PerformerProfilePrivacySchema().bind(
            request=request, context=context)
        form = deform.Form(schema, buttons=('Save',))
        rendered = None
        if 'Save' in request.POST:
            controls = request.POST.items()
            try:
                appstruct = form.validate(controls)
            except deform.ValidationFailure as e:
                rendered = e.render()
            else:
                def tf(val):
                    return val == 'true' and True or False
                context.divulge_age =  tf(appstruct['divulge_age'])
                context.divulge_realname = tf(appstruct['divulge_realname'])
                context.divulge_sex = tf(appstruct['divulge_sex'])
                context.divulge_song_likes = tf(appstruct['divulge_song_likes'])
                context.divulge_performer_likes = tf(appstruct[
                    'divulge_performer_likes'])
                context.divulge_location = tf(appstruct['divulge_location'])
                context.divulge_recording_likes = tf(appstruct[
                    'divulge_recording_likes'])
                context.divulge_genre = tf(appstruct['divulge_genre'])
                request.session.flash('Profile privacy edited', 'info')
        else:
            def tf(val):
                return val and 'true' or 'false'
            divulge_age = tf(getattr(context, 'divulge_age', True))
            divulge_realname = tf(getattr(context, 'divulge_realname', False))
            divulge_sex = tf(getattr(context, 'divulge_sex', True))
            divulge_location = tf(getattr(context, 'divulge_location', True))
            divulge_song_likes = tf(
                getattr(context, 'divulge_song_likes', True)
            )
            divulge_performer_likes = tf(
                getattr(context,'divulge_performer_likes', True)
            )
            divulge_recording_likes = tf(
                getattr(context,'divulge_recording_likes', True)
                )
            divulge_genre = tf(
                getattr(context,'divulge_genre', True)
                )
            appstruct = {
                'csrf_token': request.session.get_csrf_token(),
                'divulge_age':divulge_age,
                'divulge_realname':divulge_realname,
                'divulge_sex':divulge_sex,
                'divulge_location':divulge_location,
                'divulge_song_likes':divulge_song_likes,
                'divulge_performer_likes':divulge_performer_likes,
                'divulge_recording_likes':divulge_recording_likes,
                'divulge_genre':divulge_genre,
            }
        if rendered is None:
            rendered = form.render(appstruct, readonly=False)
        vars['form'] = rendered
        return vars


class PerformersView(object):
    default_sort = 'name'
    batch_size = 20
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
        name = find_index(context, 'system', 'name')
        num_likes = find_index(context, 'yss', 'num_likes')
        num_recordings = find_index(context, 'yss', 'num_likes')
        created = find_index(context, 'yss', 'created')
        sorting = {
            'created':(created, num_likes, num_recordings, name),
            'name':(name, num_likes, created, num_recordings),
            'likes':(num_likes, name, num_recordings, created),
            'recordings':(num_recordings, num_likes, name, created),
            }
        indexes = sorting.get(token, sorting[self.default_sort])
        for idx in indexes[1:]:
            rs = rs.sort(idx)
        first = indexes[0]
        rs = rs.sort(first, reverse=reverse)
        return rs

    @view_config(
        context=IPerformers,
        renderer='templates/performers.pt',
        permission='view',
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
        if sorting == token or (not sorting and token == 'name'):
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
            icon
            )

binary_choices = (
    ('true', 'Yes'),
    ('false', 'No'),
    )

class PerformerProfilePrivacySchema(Schema):
    divulge_age = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge your age on your profile page',
        default='true',
        )
    divulge_realname = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge your real name on your profile page',
        default='false',
        )
    divulge_sex = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge your gender on your profile page',
        default='true',
        )
    divulge_location = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge your location on your profile page',
        default='true',
        )
    divulge_song_likes = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge the songs you like on your profile page',
        default='true',
        )
    divulge_performer_likes = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge the performers you like on your profile page',
        default='false',
        )
    divulge_recording_likes = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge the recordings you like on your profile page',
        default='false',
        )
    divulge_genre = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge your favorite genre on your profile page',
        default='true',
        )

@view_config(
    context=IPerformerPhoto,
    permission='view',
#    http_cache=0, # XXX
    )
def view_file(context, request):
    return context.get_response(request=request)

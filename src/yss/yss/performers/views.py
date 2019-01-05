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

from yss.interfaces import (
    IPerformer,
    IPerformers,
    IPerformerPhoto,
    )

from yss.performers import PerformerProfileSchema

from yss.utils import get_photodata

@view_defaults(context=IPerformer)
class PerformerViews(object):
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

    def recent_recordings(self, limit=10):
        # XXX unused, kept around for instruction
        context = self.context
        request = self.request
        q = find_index(context, 'system', 'content_type').eq('Recording')
        q = q & find_index(context, 'system', 'allowed').allows(
            request, 'view')
        q = q & find_index(context, 'yss', 'performer_id').eq(context.__oid__)
        created = find_index(context, 'yss', 'created')
        resultset = q.execute()
        return resultset.sort(created, reverse=True, limit=limit)

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
                 'url':self.request.resource_url(performer, 'recordings'),
                 'class':state == 'recordings' and 'active' or '',
                 'enabled':True,
                 })
            if performer.divulge_recording_likes:
                tabs.append(
                    {'title':'Recordings Liked',
                     'id':'button-recordingsliked',
                     'url':self.request.resource_url(
                         performer, 'recordingsliked'),
                     'class':state == 'recordingsliked' and 'active' or '',
                     'enabled':True,
                    })
            if performer.divulge_song_likes:
                tabs.append(
                    {'title':'Songs Liked',
                     'id':'button-songsliked',
                     'url':self.request.resource_url(performer, 'songsliked'),
                     'class':state == 'songsliked' and 'active' or '',
                     'enabled':True,
                    })
            if performer.divulge_performer_likes:
                tabs.append(
                    {'title':'Performers Liked',
                     'id':'button-performersliked',
                     'url':self.request.resource_url(
                         performer, 'performersliked'),
                     'class':state == 'performersliked' and 'active' or '',
                     'enabled':True,
                    })

        if self.has_edit_permission:
            tabs.append(
                {'title':'Edit',
                 'id':'button-edit',
                 'url':self.request.resource_url(performer, 'edit'),
                 'class':state=='edit' and 'active' or '',
                 'enabled':True,
                 })
            tabs.append(
                {'title':'Privacy',
                 'id':'button-privacy',
                 'url':self.request.resource_url(performer, 'privacy'),
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
            'can_edit': getattr(request.user, 'performer', None) is context,
            'divulge_recording_likes': context.divulge_recording_likes,
            'divulge_performer_likes': context.divulge_performer_likes,
            'divulge_song_likes': context.divulge_song_likes,
            'divulge_age': context.divulge_age,
            'divulge_realname':context.divulge_realname,
            'divulge_location':context.divulge_location,
            'divulge_genre':context.divulge_genre,
            'divulge_sex':context.divulge_sex,
        }

    @view_config(
        renderer='templates/profile_recordings.pt',
        name='recordings',
        permission='view',
    )
    def recordings(self):
        vals = self.view()
        vals['recent_recordings'] =  self.sfilter(self.context.recordings)
        return vals

    @view_config(
        renderer='templates/profile_songsliked.pt',
        name='songsliked',
        permission='view',
    )
    def songsliked(self):
        vals = self.view()
        vals['likes_songs'] = self.sfilter(self.context.likes_songs)
        return vals

    @view_config(
        renderer='templates/profile_performersliked.pt',
        name='performersliked',
        permission='view',
    )
    def performersliked(self):
        vals = self.view()
        vals['likes_performers'] = self.sfilter(self.context.likes_performers)
        return vals

    @view_config(
        renderer='templates/profile_recordingsliked.pt',
        name='recordingsliked',
        permission='view',
    )
    def recordingsliked(self):
        vals = self.view()
        vals['likes_recordings'] = self.sfilter(self.context.likes_recordings)
        return vals

    def sfilter(self, resources):
        allowed = []
        for resource in resources:
            if self.request.has_permission('view', resource):
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
        performer = request.user.performer
        if performer in context.liked_by:
            raise HTTPBadRequest("Already")
        context.liked_by.connect([performer])
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
        performer = request.user.performer
        if performer in context.liked_by:
            context.liked_by.disconnect([performer])
        return {'ok': True,
                'num_likes': context.num_likes,
                'can_like':request.layout_manager.layout.can_like(performer),
                }

    @view_config(
        renderer='templates/profile_edit.pt',
        name='edit',
        permission='yss.edit',
    )
    def profile_edit_form(self):
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

    @view_config(
        renderer='templates/profile_privacy.pt',
        name='privacy',
        permission='yss.edit',
    )
    def profile_privacy_form(self):
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
    default_sort = 'date'
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
        name = find_index(context, 'system', 'name')
        num_likes = find_index(context, 'yss', 'num_likes')
        genre = find_index(context, 'yss', 'genre')
        created = find_index(context, 'yss', 'created')
        sorting = {
            #'date':(created, likes, title, genre),
            'date':(created,),
            'name':(name, num_likes, genre, created),
            'genre':(genre, name, num_likes, created),
            'likes':(num_likes, name, genre, created),
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
        title='Divulge your age',
        default='true',
        )
    divulge_realname = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge your real name',
        default='false',
        )
    divulge_sex = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge your gender',
        default='true',
        )
    divulge_location = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge your location',
        default='true',
        )
    divulge_song_likes = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge the songs you like',
        default='true',
        )
    divulge_performer_likes = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge the performers you like',
        default='false',
        )
    divulge_recording_likes = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge the recordings you like',
        default='false',
        )
    divulge_genre = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf([x[0] for x in binary_choices]),
        widget=deform.widget.RadioChoiceWidget(values=binary_choices),
        title='Divulge your favorite genre',
        default='true',
        )

@view_config(
    context=IPerformerPhoto,
    permission='view',
    http_cache=0, # XXX
    )
def view_file(context, request):
    return context.get_response(request=request)

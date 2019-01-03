import pytz

from pyramid_layout.layout import layout_config
from pyramid.decorator import reify
from pyramid.location import inside

from velruse import login_url

import yss.likes

@layout_config(template="templates/main_layout.pt")
class MainLayout(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def static(self, path):
        if not ':' in path:
            path = 'yss:static/' + path
        return self.request.static_url(path)

    @reify
    def twitter_login_url(self):
        return login_url(self.request, 'twitter')

    @reify
    def google_login_url(self):
        return login_url(self.request, 'google')

    def tabs(self):
        request = self.request
        context = self.context
        root = request.virtual_root
        user = request.user
        performer = None
        if user:
            performer = getattr(user, 'performer', None)
        tab_data = []
        songs = root.get('songs')
        performers = root.get('performers')
        recordings = root.get('recordings')
        for (title, section, exact, q) in (
            ('Songs', songs, None, None),
            ('Performers', performers, lambda s: context is not performer,
             None),
            ('Recordings', recordings,
             None, {'sorting':'created', 'reverse':'true'}),
            ('My Profile', performer, None, None),
            ):
            if section is not None:
                d = {}
                d['url'] = request.resource_url(section, query=q)
                d['title'] = title
                active = inside(context, section) and 'active' or None
                if exact and active:
                    active = exact(section) and 'active' or None
                d['class'] = active
                tab_data.append(d)
        return tab_data

    @property
    def batching_macro(self):
        return self.request.sdiapi.get_macro(
            'yss.root.views:templates/batching.pt',
            'batching'
            )

    def can_like(self, target):
        return yss.likes.can_like(self.request, target)

    def has_liked(self, target):
        return yss.likes.has_liked(self.request, target)

    def localize_created(self, resource):
        tzname = getattr(self.request.user, 'tzname', 'UTC')
        return resource.created.replace(tzinfo=pytz.timezone(tzname))

    def short_created_local(self, resource):
        localized = self.localize_created(resource)
        return localized.strftime('%b %d %Y')


import pytz

from pyramid_layout.layout import layout_config
from pyramid.decorator import reify
from pyramid.location import inside

from velruse import login_url

@layout_config(template="templates/main_layout.pt")
class MainLayout(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def static(self, path):
        if not ':' in path:
            path = 'yss.root.views:static/' + path
        return self.request.static_url(path)

    @reify
    def twitter_login_url(self):
        return login_url(self.request, 'twitter')

    @reify
    def google_login_url(self):
        return login_url(self.request, 'google')

    def current_performer(self):
        return self.request.performer

    def performer_thumb_url(self, performer=None):
        if performer is None:
            performer = self.current_performer()
        return self.request.resource_url(performer['photo_thumbnail'])

    def performer_photo_url(self, performer=None):
        if performer is None:
            performer = self.current_performer()
        return self.request.resource_url(performer['photo'])

    def tabs(self):
        request = self.request
        context = self.context
        root = request.virtual_root
        performer = request.performer
        tab_data = []
        songs = root.get('songs')
        performers = root.get('performers')
        for (title, section, exact, q) in (
                (
                    'Songs',
                    songs,
                    None,
                    None
                ),
                (
                    'Performers',
                    performers,
                    lambda c: performer is None or not inside(c, performer),
                    None
                ),
                (
                    'Recordings',
                    '@@recordings',
                    lambda c: c is root and request.view_name == 'recordings',
                    {'sorting':'created', 'reverse':'true'})
                ,
                (
                    'My Profile',
                    performer,
                    None,
                    None
                ),
            ):
            d = {}
            if isinstance(section, str):
                d['url'] = request.resource_url(root, section, query=q)
                d['title'] = title
                active = exact(context) and 'active' or None
                d['class'] = active
                tab_data.append(d)
            elif section is not None:
                d['url'] = request.resource_url(section, query=q)
                d['title'] = title
                active = inside(context, section) and 'active' or None
                if exact and active:
                    active = exact(context) and 'active' or None
                d['class'] = active
                tab_data.append(d)
        return tab_data

    @property
    def batching_macro(self):
        return self.request.sdiapi.get_macro(
            'yss.root.views:templates/batching.pt',
            'batching'
            )

    @property
    def profile_header_macro(self):
        return self.request.sdiapi.get_macro(
            'yss.performers:templates/profile_header.pt',
            'profile_header'
            )

    @property
    def likes_macro(self):
        return self.request.sdiapi.get_macro(
            'yss.root.views:templates/likes.pt',
            'likes'
            )

    def can_like(self, resource):
        request = self.request
        if not self.has_liked(resource):
            return request.has_permission('yss.like', resource)

    def has_liked(self, resource):
        request = self.request
        performer = request.performer
        if performer is not None:
            return performer in resource.liked_by

    def localize_created(self, resource):
        tzname = getattr(self.request.user, 'tzname', 'UTC')
        return resource.created.replace(tzinfo=pytz.timezone(tzname))

    def short_created_local(self, resource):
        localized = self.localize_created(resource)
        return localized.strftime('%b %d %Y')

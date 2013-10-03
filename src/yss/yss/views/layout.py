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
            path = 'yss:static/' + path
        return self.request.static_url(path)

    @reify
    def twitter_login_url(self):
        return login_url(self.request, 'twitter')

    def tabs(self):
        request = self.request
        context = self.context
        root = request.virtual_root
        user = request.user
        performer = None
        if user:
            performer = getattr(user, 'performer', None)
        home_data = {
            'url':request.resource_url(root),
            'title':'Home',
            'class':context is root and 'active' or None
            }
        tab_data = [ home_data ]
        songs = root.get('songs')
        performers = root.get('performers')
        recordings = root.get('recordings')
        for (title, section, exact) in (
            ('Songs', songs, None),
            ('Performers', performers, lambda s: context is not performer),
            ('Recordings', recordings, None),
            ('My Profile', performer, None),
            ):
            if section is not None:
                d = {}
                d['url'] = request.resource_url(section)
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
            'yss.views:templates/batching.pt',
            'batching'
            )

    def can_like(self, target=None):
        user = self.request.user
        if user is not None:
            performer = user.performer
            if performer is not None:
                if target is None:
                    target = self.context
                return performer not in target.liked_by

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
        root = self.request.virtual_root
        home_data = {
            'url':self.request.resource_url(root),
            'title':'Home',
            'class':self.context is root and 'active' or None
            }
        tab_data = [ home_data ]
        songs = root.get('songs')
        performers = root.get('performers')
        recordings = root.get('recordings')
        for (title, section) in (
            ('Songs', songs),
            ('Performers', performers),
            ('Recordings', recordings),
            ):
            if section is not None:
                d = {}
                d['url'] = self.request.resource_url(section)
                d['title'] = title
                d['class'] = inside(self.context, section) and 'active' or None
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

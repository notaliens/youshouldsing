from pyramid_layout.layout import layout_config
from pyramid.decorator import reify
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
        

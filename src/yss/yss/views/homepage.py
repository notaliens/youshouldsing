from pyramid.view import view_config
from substanced.util import find_index

class HomepageView(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def featured_recordings(self, limit=10):
        request = self.request
        context = self.context
        q = find_index(context, 'system', 'content_type').eq('Recording')
        q = q & find_index(context, 'system', 'allowed').allows(
            request, 'view')
        likes = find_index(context, 'yss', 'likes')
        resultset = q.execute()
        return resultset.sort(likes, reverse=True, limit=limit)

    def recent_recordings(self, limit=10):
        request = self.request
        context = self.context
        q = find_index(context, 'system', 'content_type').eq('Recording')
        q = q & find_index(context, 'system', 'allowed').allows(
            request, 'view')
        created = find_index(context, 'yss', 'created')
        resultset = q.execute()
        return resultset.sort(created, reverse=True, limit=limit)

    @view_config(renderer="templates/home.pt")
    def home(self):
        return {'featured_recordings': self.featured_recordings(),
                'recent_recordings': self.recent_recordings(),
               }

from pyramid.view import view_config
from velruse import login_url

@view_config(renderer="templates/home.pt")
def home(request):
    return {
        'twitter_login_url': login_url(request, 'twitter'),
        }

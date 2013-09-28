from pyramid.view import view_config
from pyramid.response import Response

@view_config()
def itworks(request):
    return Response('It works!')

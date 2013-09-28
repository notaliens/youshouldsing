import os
import random
import shutil

from pyramid.view import view_config
from velruse import login_url

random.seed()

@view_config(renderer="templates/home.pt")
def home(request):
    return {
        'twitter_login_url': login_url(request, 'twitter'),
        }

@view_config(name="record",
             renderer="templates/record.pt")
def recording_app(request):
    performance_id = generate_performance_id({})
    return {
        "id": performance_id,
    }


@view_config(name="record", xhr=True, renderer='string')
def save_recording(request):
    f = request.params['data'].file
    id = request.params['id']
    fname = request.params['filename']
    tmpdir = '/tmp/' + id
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    with open('%s/%s' % (tmpdir, fname), 'wb') as output:
        shutil.copyfileobj(f, output)
    return 'OK'


idchars = (
    map(chr, range(ord('a'), ord('z') + 1)) +
    map(chr, range(ord('A'), ord('Z') + 1)) +
    map(chr, range(ord('0'), ord('9') + 1)))


def generate_performance_id(performances):
    while True:
        id = ''.join([random.choice(idchars) for _ in range(8)])
        if id not in performances:
            break
    return id


@view_config(
    context='velruse.AuthenticationComplete',
    renderer='templates/logged_in.pt',
)
def login_complete_view(context, request):
    return {
        'ok': True,
        'provider_type': context.provider_type,
        'provider_name': context.provider_name,
        'profile': context.profile,
        'credentials': context.credentials,
    }

@view_config(
    context='velruse.AuthenticationDenied',
    renderer='templates/logged_in.pt',
)
def login_denied_view(context, request):
    return {
        'ok': False,
        'provider_name': context.provider_name,
        'reason': context.reason,
    }

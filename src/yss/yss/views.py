import base64
import uuid

from pyramid.view import view_config
from velruse import login_url

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


@view_config(name="record", xhr=True)
def save_recording(request):
    pass


def generate_performance_id(performances):
    while True:
        id = base64.b64encode(uuid.uuid4().bytes).rstrip("==")[-8:]
        if id not in performances:
            break
    return id


@view_config(
    context='velruse.AuthenticationComplete',
    renderer='templates/logged_in.pt',
)
def login_complete_view(context, request):
    import pdb; pdb.set_trace()
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
    import pdb; pdb.set_trace()
    return {
        'ok': False,
        'provider_name': context.provider_name,
        'reason': context.reason,
    }

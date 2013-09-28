import base64
import uuid

from pyramid.view import view_config
from velruse import login_url


@view_config(renderer="templates/splash.pt"
            )
def itworks(request):
    return {'twitter_login_url': login_url(request, 'twitter'),
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

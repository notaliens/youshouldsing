import datetime
import pkg_resources

from pyramid.threadlocal import get_current_request

from pyramid.security import (
    Allow,
    Everyone,
    Authenticated,
    )

from substanced.event import (
    subscribe_added,
    subscribe_root_added,
    subscribe_will_be_added,
    )

from substanced.util import set_acl

@subscribe_root_added()
def root_added(event):
    registry = event.registry
    root = event.object
    acl = list(root.__acl__)
    acl.extend(
        [
        (Allow, Everyone, 'view'),
        (Allow, Authenticated, 'yss.record'),
        (Allow, Authenticated, 'yss.like'),
        ]
    )
    set_acl(root, acl)
    root.title = root.sdi_title = 'You Should Sing'
    root['catalogs'].add_catalog('yss')
    root['songs'] = registry.content.create('Songs')
    root['performers'] = registry.content.create('Performers')
    root['recordings'] = registry.content.create('Recordings')
    timings_json = pkg_resources.resource_string(
        'yss', 'blackbird.json').decode('utf-8')
    song = registry.content.create(
        'Song',
        'Blackbird',
        'The Beatles',
        timings=timings_json,
        lyrics=timings_json,
        audio_stream=pkg_resources.resource_stream('yss', 'blackbird.mp3')
    )
    root['songs']['blackbird'] = song

@subscribe_will_be_added()
def content_will_be_added(event):
    event.object.created = datetime.datetime.utcnow()
    

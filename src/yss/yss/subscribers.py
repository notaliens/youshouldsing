import datetime
import pkg_resources
import pytz

from pyramid.security import (
    Allow,
    Everyone,
    Authenticated,
    )

from substanced.event import (
    subscribe_root_added,
    subscribe_will_be_added,
    subscribe_will_be_removed,
    subscribe_removed,
    )

from substanced.util import (
    set_acl,
    find_service,
    )

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
    event.object.created = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    
@subscribe_will_be_removed(content_type='Performer')
def performer_will_be_removed(event):
    # delete recordings made by the performer when we delete a performer.
    # see performer_removed for further stupid, where we delete the
    # principal associated with the performer.

    if event.moving is not None: # it's not really being removed
        return

    performer = event.object

    for recording in performer.recordings:
        recording.__parent__.remove(recording.__name__)


@subscribe_removed(content_type='Performer')
def performer_removed(event):
    # delete principal associated with performer. we can't do this in
    # performer_will_be_removed because of the PrincipalToACLBearing
    # relationship source_integrity (the principal hasn't yet been deleted, so
    # we can't delete the user).  XXX Note that this is insanity, we need
    # cascading deletes in substanced instead of this ghetto version where we
    # split these associated ops across events.

    if event.moving is not None:
        return

    principals = find_service(event.parent, 'principals')
    users = principals['users']
    if event.name in users:
        users.remove(event.name)
    

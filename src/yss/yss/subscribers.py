import datetime
import pytz

from substanced.event import (
    subscribe_will_be_added,
    subscribe_will_be_removed,
    subscribe_removed,
    )

from substanced.util import find_service

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
    

import datetime
import pkg_resources

from pyramid.threadlocal import get_current_request

from pyramid.security import (
    Allow,
    Everyone,
    )

from substanced.event import (
    subscribe_added,
    subscribe_root_added,
    subscribe_will_be_added,
    )

from substanced.util import (
    get_oid,
    find_catalog,
    )

@subscribe_root_added()
def root_added(event):
    registry = event.registry
    root = event.object
    root.title = root.sdi_title = 'You Should Sing'
    root['catalogs'].add_catalog('yss')
    root['songs'] = registry.content.create('Songs')
    root['performers'] = registry.content.create('Performers')
    root['recordings'] = registry.content.create('Recordings')
    song = registry.content.create(
        'Song', 'Blackbird', 'The Beatles',
        pkg_resources.resource_string('yss', 'blackbird.json'),
        pkg_resources.resource_stream('yss', 'blackbird.mp3'))
    root['songs']['blackbird'] = song
    acl = list(root.__acl__)
    acl.append((Allow, Everyone, 'view'))
    root.__acl__ = acl

@subscribe_will_be_added()
def content_will_be_added(event):
    event.object.created = datetime.datetime.utcnow()
    
@subscribe_added()
def content_added(event):
    request = get_current_request()
    creator_id = get_oid(getattr(request, 'user', None), None)
    event.object.creator_id = creator_id
    catalog = find_catalog(event.object, 'yss')
    if catalog:
        index = catalog.get('creator_id')
        if index:
            index.reindex_resource(event.object)

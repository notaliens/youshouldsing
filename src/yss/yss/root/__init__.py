import pkg_resources

from substanced.schema import Schema
from substanced.property import PropertySheet
from substanced.interfaces import IRoot

import colander

from pyramid.security import (
    Allow,
    Everyone,
    Authenticated,
    )

from substanced.event import subscribe_root_added

from substanced.util import set_acl

class RootSchema(Schema):
    """ The schema representing site properties. """
    max_framerate = colander.SchemaNode(
        colander.Int(),
        title="Max Frame Rate",
        missing=1,
        )

class RootPropertySheet(PropertySheet):
    schema = RootSchema()

@subscribe_root_added()
def root_added(event):
    registry = event.registry
    root = event.object
    acl = list(root.__acl__)
    acl.extend(
        [
        (Allow, Everyone, 'view'),
        (Allow, Everyone, 'yss.indexed'),
        (Allow, Authenticated, 'yss.like'),
        ]
    )
    set_acl(root, acl)
    root.title = root.sdi_title = 'You Should Sing'
    root['catalogs'].add_catalog('yss')
    root['songs'] = registry.content.create('Songs')
    set_acl(root['songs'], [
        (Allow, Authenticated, 'yss.upload'),
        (Allow, Authenticated, 'yss.record'),
    ])
    root['performers'] = registry.content.create('Performers')
    root.max_framerate = 30
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

def performer(request):
    user = request.user
    if user is not None:
        return user.performer

def includeme(config):
    config.add_propertysheet('YSS', RootPropertySheet, IRoot)
    config.add_request_method(performer, reify=True)
    

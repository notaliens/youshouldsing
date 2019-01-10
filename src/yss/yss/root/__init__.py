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
    root.max_framerate = 30

    root['catalogs'].add_catalog('yss')

    root['songs'] = registry.content.create('Songs')
    set_acl(root['songs'], [
        (Allow, Authenticated, 'yss.upload'),
        (Allow, Authenticated, 'yss.record'),
    ])

    performers = root['performers'] = registry.content.create('Performers')

    blameme = registry.content.create('Performer')
    performers['blameme'] = blameme
    blameme['recordings'] = registry.content.create('Recordings')
    blameme['photo'] = registry.content.create('File')
    blameme['photo_thumbnail'] = registry.content.create('File')

    blameme.user = root['principals']['users']['admin']

    timings_json = pkg_resources.resource_string(
        'yss', 'blackbird.json').decode('utf-8')
    song = registry.content.create(
        'Song',
        'Blackbird',
        'The Beatles',
        timings=timings_json,
        lyrics=timings_json,
        audio_stream=pkg_resources.resource_stream('yss', 'blackbird.opus')
    )
    root['songs']['blackbird'] = song
    song.mimetype = 'audio/opus'
    song.uploader = blameme

def performer(request):
    user = request.user
    if user is not None:
        return user.performer

def includeme(config):
    config.add_propertysheet('YSS', RootPropertySheet, IRoot)
    config.add_request_method(performer, reify=True)
    

import pkg_resources
from pyramid.threadlocal import get_current_registry
from pyramid.security import (
    Allow,
    Everyone,
    Authenticated,
    )
from substanced.util import set_acl

def add_sections(root):
    registry = get_current_registry()
    root['songs'] = registry.content.create('Songs')
    root['performers'] = registry.content.create('Performers')
    root['recordings'] = registry.content.create('Recordings')

def add_test_song(root):
    # Workaround
    if 'songs' not in root:
        add_sections(root)
    registry = get_current_registry()
    timings_json = pkg_resources.resource_string(
        'yss', 'blackbird.json').decode('utf-8')
    song = registry.content.create(
        'Song',
        'Blackbird',
        'The Beatles',
        timings=timings_json,
        lyrics=timings_json,
        audio_stream=pkg_resources.resource_stream('yss', 'blackbird.mp3'),
    )
    root['songs']['blackbird'] = song

def change_site_title(root):
    root.title = root.sdi_title = 'You Should Sing'

def add_permissions(root):
    acl = list(root.__acl__)
    acl.extend(
        [
        (Allow, Everyone, 'view'),
        (Allow, Authenticated, 'yss.record'),
        (Allow, Authenticated, 'yss.like'),
        ]
    )
    set_acl(root, acl)
    
def add_yss_catalog(root):
    if not 'yss' in root['catalogs']:
        root['catalogs'].add_catalog('yss')

def includeme(config):
    config.add_evolution_step(add_sections)
    config.add_evolution_step(add_test_song)
    config.add_evolution_step(change_site_title)
    config.add_evolution_step(add_yss_catalog)
    config.add_evolution_step(add_permissions)
    

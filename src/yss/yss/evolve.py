import pkg_resources
from pyramid.threadlocal import get_current_registry


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
    song = registry.content.create(
        'Song', 'Blackbird', 'The Beatles',
        pkg_resources.resource_string('yss', 'blackbird.json'),
        pkg_resources.resource_stream('yss', 'blackbird.mp3'))
    root['songs']['blackbird'] = song

def change_site_title(root):
    root.title = root.sdi_title = 'You Should Sing'

def add_yss_catalog(root):
    root['catalogs'].add_catalog('yss')

def includeme(config):
    config.add_evolution_step(add_sections)
    config.add_evolution_step(add_test_song)
    config.add_evolution_step(change_site_title)
    config.add_evolution_step(add_yss_catalog)
    

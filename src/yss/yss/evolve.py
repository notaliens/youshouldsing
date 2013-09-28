from pyramid.threadlocal import get_current_registry

def add_sections(root):
    registry = get_current_registry()
    root['songs'] = registry.content.create('Songs')
    root['performers'] = registry.content.create('Performers')
    root['recordings'] = registry.content.create('Recordings')

def includeme(config):
    config.add_evolution_step(add_sections)
    

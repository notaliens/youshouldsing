import time

from substanced.catalog import (
    catalog_factory,
    Field
    )

@catalog_factory('yss')
class Indexes(object):
    genre = Field()
    title = Field()
    artist = Field()
    likes = Field()
    creator_id = Field()
    created = Field()

class IndexViews(object):
    def __init__(self, resource):
        self.resource = resource

    def tolower(self, val, default):
        if val in (default, None):
            return val
        return val.lower()

    def title(self, default):
        title = getattr(self.resource, 'title', default)
        return self.tolower(title, default)

    def genre(self, default):
        genre = getattr(self.resource, 'genre', default)
        return self.tolower(genre, default)
        
    def artist(self, default):
        artist = getattr(self.resource, 'artist', default)
        return self.tolower(artist, default)

    def likes(self, default):
        return getattr(self.resource, 'likes', default)

    def creator_id(self, default):
        return getattr(self.resource, 'creator_id', default)

    def created(self, default):
        created = getattr(self.resource, 'created', None)

        # we can't store datetimes directly in the catalog because they
        # can't be compared with anything

        if created is None:
            created = 0
        else:
            timetime = time.mktime(created.timetuple())
            # creation "minute" actually to prevent too-granular storage
            created = int(str(int(timetime))[:-2])

        return created
    
def includeme(config):  # pragma: no cover
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='title',
        attr='title',
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='genre',
        attr='genre',
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='artist',
        attr='artist',
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='likes',
        attr='likes',
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='creator_id',
        attr='creator_id',
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='created',
        attr='created',
        )

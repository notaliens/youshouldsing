import time

from substanced.catalog import (
    catalog_factory,
    Field,
    Text,
    )

from yss.interfaces import (
    IRecording,
    ISong,
    )

@catalog_factory('yss')
class Indexes(object):
    genre = Field()
    title = Field()
    artist = Field()
    num_likes = Field()
    num_recordings = Field()
    creator_id = Field()
    created = Field()
    performer = Field()
    duration = Field() # in seconds
    lyrics = Text()

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

    def duration(self, default):
        duration = getattr(self.resource, 'duration', default)
        return duration # intent: in seconds

    def genre(self, default):
        genre = getattr(self.resource, 'genre', default)
        return self.tolower(genre, default)

    def artist(self, default):
        artist = getattr(self.resource, 'artist', default)
        return self.tolower(artist, default)

    def performer(self, default):
        performer = getattr(self.resource, 'performer', default)
        performer_title = getattr(performer, 'title', default)
        return self.tolower(performer_title, default)

    def num_likes(self, default):
        return getattr(self.resource, 'num_likes', default)

    def num_recordings(self, default):
        return getattr(self.resource, 'num_recordings', default)

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

    def lyrics(self, default):
        return getattr(self.resource, 'lyrics', default)

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
        index_name='num_likes',
        attr='num_likes',
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
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='performer',
        attr='performer',
        context = IRecording,
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='duration',
        attr='duration',
        context = ISong,
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='num_recordings',
        attr='num_recordings',
        context = ISong,
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='lyrics',
        attr='lyrics',
        context = ISong,
        )

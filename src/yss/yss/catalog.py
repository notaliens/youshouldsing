import time

from pyramid.threadlocal import get_current_request

from substanced.catalog import (
    catalog_factory,
    Field,
    Text,
    )

from substanced.workflow import get_workflow

from yss.interfaces import (
    IRecording,
    ISong,
    IPerformer,
    )

@catalog_factory('yss')
class Indexes(object):
    genre = Field()
    title = Field()
    artist = Field()
    num_likes = Field()
    num_views = Field()
    num_recordings = Field()
    performer_id = Field()
    created = Field()
    performer = Field()
    duration = Field() # in seconds
    lyrics = Text()
    text = Text()
    visibility_state = Field()
    oid = Field()
    mixed = Field()

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

    def num_views(self, default):
        num_views = getattr(self.resource, 'num_views', None)
        if num_views is None:
            return default
        return num_views()

    def num_recordings(self, default):
        return getattr(self.resource, 'num_recordings', default)

    def performer_id(self, default):
        return getattr(self.resource.performer, '__oid__', default)

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

    def mixed(self, default):
        return getattr(self.resource, 'mixed', False)

    def lyrics(self, default):
        return getattr(self.resource, 'lyrics', default)

    def recording_text(self, default):
        song = self.resource.song
        return song.title + ' ' + song.artist

    def performer_text(self, default):
        performer = self.resource
        return performer.__name__

    def song_text(self, default):
        song = self.resource
        return song.title + ' ' + song.artist

    def visibility_state(self, default):
        request = get_current_request()
        visibility_wf = get_workflow(request, 'Visibility', 'Recording')
        return visibility_wf.state_of(self.resource)

    def oid(self, default):
        return getattr(self.resource, '__oid__', default)

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
        index_name='oid',
        attr='oid',
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='performer_id',
        attr='performer_id',
        context=IRecording,
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
        index_name='text',
        attr='recording_text',
        context = IRecording,
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='text',
        attr='performer_text',
        context = IPerformer,
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='text',
        attr='song_text',
        context = ISong,
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='visibility_state',
        attr='visibility_state',
        context = IRecording,
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='num_views',
        attr='num_views',
        context = IRecording,
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='mixed',
        attr='mixed',
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
        index_name='num_recordings',
        attr='num_recordings',
        context = IPerformer,
        )
    config.add_indexview(
        IndexViews,
        catalog_name='yss',
        index_name='lyrics',
        attr='lyrics',
        context = ISong,
        )

import colander
import slug

from pyramid.httpexceptions import HTTPFound
from substanced.form import FormView
from substanced.file import FileNode
from substanced.schema import Schema
from substanced.sdi import mgmt_view

from .interfaces import ISongs


class AddSongSchema(Schema):
    title = colander.SchemaNode(colander.String())
    artist = colander.SchemaNode(colander.String())
    timing = colander.SchemaNode(colander.String())
    file = FileNode()


@mgmt_view(context=ISongs,
           name='add_song',
           tab_title='Add Song',
           permission='sdi.add-content',
           renderer='substanced.sdi:templates/form.pt',
           tab_condition=False)
class AddSongView(FormView):
    title = 'Add Song'
    schema = AddSongSchema()
    buttons = ('add',)

    def add_success(self, appstruct):
        title = appstruct['title']
        artist = appstruct['artist']
        timing = appstruct['timing']
        name = slug.slug(title)
        stream = appstruct['file']['fp']
        song = self.request.registry.content.create(
            'Song', title, artist, timing, stream)
        self.context[name] = song
        return HTTPFound(self.request.sdiapi.mgmt_path(self.context))


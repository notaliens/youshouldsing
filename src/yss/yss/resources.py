import colander
import deform
from substanced.content import content
from substanced.folder import Folder
from substanced.interfaces import IUser
from substanced.interfaces import UserToGroup
from substanced.objectmap import multireference_source_property
from substanced.objectmap import multireference_sourceid_property
from substanced.principal import UserPropertySheet
from substanced.principal import UserGroupsPropertySheet
from substanced.schema import Schema
from substanced.util import renamer
from zope.interface import implementer

_sex_choices = (('', '- Select -'),
                ('female', 'Female'),
                ('male', 'Male')
               )

_genre_choices = (('', '- Select -'),
                  ('rock', 'Rock'),
                  ('pop', 'Pop'),
                  ('country', 'Country'),
                  ('jazz', 'Jazz'),
                  ('blues', 'Blues'),
                 )

class YSSProfileSchema(Schema):
    """ Property schema for :class:`substanced.principal.User` objects.
    """
    display_name = colander.SchemaNode(
        colander.String(),
    )
    email = colander.SchemaNode(
        colander.String(),
        validator=colander.All(
            colander.Email(),
            colander.Length(max=100)
            ),
        )
    photo_url = colander.SchemaNode(
        colander.String(),
        title='Photo URL',
        validator=colander.url,
        )
    age = colander.SchemaNode(
        colander.Int(),
        title='Age',
        validator=colander.Range(min=0, max=150),
        )
    sex = colander.SchemaNode(
        colander.String(),
        title='Sex',
        widget=deform.widget.SelectWidget(values=_sex_choices),
    )
    favorite_genre = colander.SchemaNode(
        colander.String(),
        title='Favorite Genre',
        widget=deform.widget.SelectWidget(values=_genre_choices),
    )

@content(
    'User',
    icon='glyphicon glyphicon-user',
    add_view='add_user',
    tab_order=('properties',),
    propertysheets = (
        ('Preferences', UserPropertySheet),
        ('Groups', UserGroupsPropertySheet),
        )
    )
@implementer(IUser)
class User(Folder):
    tzname = 'UTC' # backwards compatibility default
    groupids = multireference_sourceid_property(UserToGroup)
    groups = multireference_source_property(UserToGroup)
    name = renamer()

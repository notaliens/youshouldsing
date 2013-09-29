# Retail profile views
import colander
import deform

from pyramid.view import view_config

from ..interfaces import IPerformer
from ..resources import PerformerProfileSchema

@view_config(
    context=IPerformer,
    renderer='templates/profile.pt',
)
def profile_view(context, request):
    return {
        'username': context.__name__,
        'display_name': getattr(context, 'display_name', ''),
        'email': getattr(context, 'email', ''),
        'photo_url': getattr(context, 'photo_url', ''),
        'age': getattr(context, 'age', colander.null),
        'sex': getattr(context, 'sex', None),
        'favorite_genre': getattr(context, 'favorite_genre', None),
        'form': None
    }
    form = deform.Form(PerformerProfileSchema(), buttons=('Save',))

@view_config(
    context=IPerformer,
    renderer='templates/profile.pt',
    name='edit.html',
#    permission='edit', XXX
)
def profile_edit_form(context, request):
    schema = PerformerProfileSchema().bind(request=request, context=context)
    form = deform.Form(schema, buttons=('Save',))
    rendered = None
    if 'Save' in request.POST:
        controls = request.POST.items()
        try:
            appstruct = form.validate(controls)
        except deform.ValidationFailure as e:
            rendered = e.render()
        else:
            context.display_name = appstruct['display_name']
            context.email = appstruct['email']
            context.photo_url = appstruct['photo_url']
            context.age = appstruct['age']
            context.sex = appstruct['sex']
            context.favorite_genre = appstruct['favorite_genre']
    else:
        appstruct = {
            'csrf_token': request.session.get_csrf_token(),
            'username': context.__name__,
            'display_name': getattr(context, 'display_name', ''),
            'email': getattr(context, 'email', ''),
            'photo_url': getattr(context, 'photo_url', ''),
            'age': getattr(context, 'age', colander.null),
            'sex': getattr(context, 'sex', None),
            'favorite_genre': getattr(context, 'favorite_genre', None),
        }
    if rendered is None:
        rendered = form.render(appstruct, readonly=False)
    return {
        'form': rendered,
    }

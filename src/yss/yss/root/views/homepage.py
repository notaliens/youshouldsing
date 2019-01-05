from pyramid.view import view_config
from substanced.util import find_index

class HomepageView(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def featured_recordings(self, limit=10):
        request = self.request
        context = self.context
        q = find_index(context, 'system', 'content_type').eq('Recording')
        q = q & find_index(context, 'system', 'allowed').allows(
            request, 'yss.indexed')
        num_likes = find_index(context, 'yss', 'num_likes')
        resultset = q.execute()
        return resultset.sort(num_likes, reverse=True, limit=limit)

    def recent_recordings(self, limit=10):
        request = self.request
        context = self.context
        q = find_index(context, 'system', 'content_type').eq('Recording')
        q = q & find_index(context, 'system', 'allowed').allows(
            request, 'yss.indexed')
        created = find_index(context, 'yss', 'created')
        resultset = q.execute()
        return resultset.sort(created, reverse=True, limit=limit)

    @view_config(renderer="templates/home.pt")
    def home(self):
        return {'featured_recordings': self.featured_recordings(),
                'recent_recordings': self.recent_recordings(),
               }


@view_config(name='tos', renderer="templates/tos.pt")
def terms_of_service_view(context, request):
    return {'tos':tos}

tos = """Terms of Service

Welcome to our website. If you continue to browse and use this website, you are
agreeing to comply with and be bound by the following terms and conditions of
use, which together with our privacy policy govern You Should Sing's
relationship with you in relation to this website. If you disagree with any
part of these terms and conditions, please do not use our website.

The term 'You Should Sing' or 'us' or 'we' refers to the owner of the website
whose registered office is in Fredericksburg, VA, USA.  The term 'you' refers
to the user or viewer of our website.

The use of this website is subject to the following terms of use:

- The content of the pages of this website is for your general information and
  use only. It is subject to change without notice.

- This website uses cookies to monitor browsing preferences. If you do allow
  cookies to be used, the following personal information may be stored by us
  for use by third parties: email address, real name, various service
  identifiers for login.

- Neither we nor any third parties provide any warranty or guarantee as to the
  accuracy, timeliness, performance, completeness or suitability of the
  information and materials found or offered on this website for any particular
  purpose. You acknowledge that such information and materials may contain
  inaccuracies or errors and we expressly exclude liability for any such
  inaccuracies or errors to the fullest extent permitted by law.

- Your use of any information or materials on this website is entirely at your
  own risk, for which we shall not be liable. It shall be your own
  responsibility to ensure that any products, services or information available
  through this website meet your specific requirements.

- This website contains material which is owned by or licensed to us. This
  material includes, but is not limited to, the design, layout, look,
  appearance and graphics. Reproduction is prohibited other than in accordance
  with the copyright notice, which forms part of these terms and conditions.

- All trade marks reproduced in this website which are not the property of, or
  licensed to, the operator are acknowledged on the website.

- Unauthorised use of this website may give rise to a claim for damages and/or
  be a criminal offense.

- From time to time this website may also include links to other
  websites. These links are provided for your convenience to provide further
  information. They do not signify that we endorse the website(s). We have no
  responsibility for the content of the linked website(s).

- Your use of this website and any dispute arising out of such use of the
  website is subject to the laws of Fredericksburg, VA, USA.

"""

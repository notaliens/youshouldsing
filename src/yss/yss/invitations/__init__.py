import random
import string

from persistent import Persistent

from pyramid.threadlocal import get_current_registry

from substanced.content import content
from substanced.objectmap import reference_source_property
from substanced.folder import Folder

from substanced.util import find_index

from zope.interface import implementer

from yss.interfaces import (
    InvitationToRedeemer,
    IInvitations,
    IInvitation,
    )


@content(
    'Invitations',
    icon='glyphicon glyphicon-list-alt',
    )
@implementer(IInvitations)
class Invitations(Folder):
    def add_more(self, num):
        ctindex = find_index(self, 'system', 'content_type')
        nameindex = find_index(self, 'system', 'name')
        baseq = ctindex.eq('Invitation')
        i = 0
        while True:
            invite_id = ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=8))
            q = baseq & nameindex.eq(invite_id)
            # dont create more than one invite with the same name globally
            rs = q.execute()
            if len(rs):
                continue
            invitation = get_current_registry().content.create('Invitation')
            self[invite_id] = invitation
            i+=1
            if i>=num:
                break

@content(
    'Invitation',
    icon='glyphicon glyphicon-envelope',
    #add_view='add_invitation',
    #tab_order=('properties',),
    #propertysheets = (),
    )
@implementer(IInvitation)
class Invitation(Persistent):
    redeemer = reference_source_property(InvitationToRedeemer)
    redemption_date = None

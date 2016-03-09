#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Directives to be used in ZCML: registering static course invitations with known codes.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.configuration.fields import TextLine

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.invitation import JoinCourseInvitation

from nti.invitations.interfaces import IInvitations

class IRegisterJoinCourseInvitationDirective(interface.Interface):
    """
    The arguments needed for registering an invitation to join communities.
    """

    code = TextLine(
        title="The human readable/writable code the user types in. Should not have spaces.",
        required=True,
        )

    course = TextLine(
        title="The NTIID of the course to join",
        required=True,
        )
    
    scope = TextLine(
        title="The enrollment scope",
        required=False,
        )

def _register(code, course, scope=ES_PUBLIC):
    invitations = component.getUtility(IInvitations)
    invitations.registerInvitation(JoinCourseInvitation(code, course, scope))

def registerJoinCourseInvitation(_context, code, course, scope=ES_PUBLIC):
    """
    Register an invitation with the given code that, at runtime,
    will resolve and try to enroll in the named course.

    :param module module: The module to inspect.
    """
    _context.action(discriminator=('registerJoinCourseInvitation', code),
                    callable=_register,
                    args=(code, course, scope))

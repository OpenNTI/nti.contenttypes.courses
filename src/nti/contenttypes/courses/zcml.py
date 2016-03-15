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

from zope.component.zcml import utility

from zope.configuration.fields import TextLine

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_NAMES

from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

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

def _register(_context, code, course, scope=ES_PUBLIC):
	invitations = component.queryUtility(IInvitations)
	if invitations is not None:
		# register w/ invitations
		invitation = JoinCourseInvitation(code, course, scope)
		invitations.registerInvitation(invitation)
		# register as a utility
		utility(_context,
				provides=IJoinCourseInvitation,
				component=invitation,
				name=code)
		logger.info('Course invitation "%s" has been registered', code)

def registerJoinCourseInvitation(_context, code, course, scope=ES_PUBLIC):
	"""
	Register an invitation with the given code that, at runtime,
	will resolve and try to enroll in the named course.

	:param module module: The module to inspect.
	"""
	scope = scope or ES_PUBLIC
	assert scope in ENROLLMENT_SCOPE_NAMES, 'Invalid scope'

	_register(_context, code, course, scope)

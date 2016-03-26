#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contenttypes.courses import MessageFactory as _

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import IJoinCourseInvitationActor

from nti.contenttypes.courses.utils import get_enrollment_in_hierarchy

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.invitations.invitation import ActorZcmlInvitation

from nti.ntiids.ntiids import find_object_with_ntiid

@interface.implementer(IJoinCourseInvitationActor)
class JoinCourseInvitationActor(object):
	"""
	Default enrollment course invitation actor utility
	it should be registered per site
	"""

	def accept(self, user, entry, scope=None):
		scope = scope or ES_PUBLIC
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is None:
			raise ValueError(_("Course catalog not available."))

		# find course
		course = find_object_with_ntiid(entry)
		if course is None:
			course = catalog.getCatalogEntry(entry)

		course = ICourseInstance(course, None)
		if course is None:
			raise ValueError(_("Course not found."))

		record = get_enrollment_in_hierarchy(course, user)
		if record is not None:
			raise ValueError(_("User already enrolled in course."))

		enrollment_manager = ICourseEnrollmentManager(course)
		enrollment_manager.enroll(user, scope=scope)
		return True

@interface.implementer(IJoinCourseInvitation)
class JoinCourseInvitation(ActorZcmlInvitation):
	"""
	Simple first pass at a pre-configured invitation to enroll in a
	course. Intended to be configured with ZCML and not stored persistently.
	"""

	creator = SYSTEM_USER_NAME
	actor_interface = IJoinCourseInvitationActor

	def __init__(self, code, course, scope=None):
		super(JoinCourseInvitation, self).__init__()
		self.code = code
		self.course = course
		self.scope = scope or ES_PUBLIC

	def accept(self, user):
		actor = component.getUtility(self.actor_interface)
		if actor.accept(user, self.course, self.scope):
			super(JoinCourseInvitation, self).accept(user)
			return True
		return False


#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ACL providers for course data.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from .interfaces import ICourseInstance
from .interfaces import ES_PUBLIC
from .interfaces import ES_CREDIT
from .interfaces import INonPublicCourseInstance
from .interfaces import ICourseCatalogEntry

from zope.security.interfaces import IPrincipal

from nti.dataserver.interfaces import IACLProvider

from nti.utils.property import Lazy

from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME
from nti.dataserver.interfaces import EVERYONE_GROUP_NAME
from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import ace_denying
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CREATE


@component.adapter(ICourseInstance)
@interface.implementer(IACLProvider)
class CourseInstanceACLProvider(object):
	"""
	Provides the basic ACL for a course instance.

	This cooperates with the course's principal map to provide
	the full access control.

	We typically expect the course catalog entry for this object
	to be a child and inherit the same ACL.
	"""

	def __init__(self, context):
		self.context = context

	@Lazy
	def __acl__(self):
		course = self.context

		sharing_scopes = course.SharingScopes
		sharing_scopes.initScopes()
		main_scope = sharing_scopes[ES_PUBLIC]
		if INonPublicCourseInstance.providedBy(course):
			main_scope = sharing_scopes[ES_CREDIT]

		acl = acl_from_aces(
				ace_allowing( IPrincipal(main_scope), ACT_READ, CourseInstanceACLProvider )
		)
		acl.extend( (ace_allowing( i, ACT_READ, CourseInstanceACLProvider )
					 for i in course.instructors) )
		return acl

from nti.dataserver.traversal import find_interface

@component.adapter(ICourseCatalogEntry)
@interface.implementer(IACLProvider)
class CourseCatalogEntryACLProvider(object):
	"""
	Provides the ACL for course catalog entries.

	If the ACL is in the context of a non-public
	course instance, then no ACL opinion is offered (we simply
	inherit (if we have a course in our lineage; for BWC, if we do not,
	we lock it down hard)). Otherwise, even if you're not enrolled
	in the course, we allow all authenticated users to view the
	catalog.
	"""

	def __init__(self, context):
		self.context = context

	@Lazy
	def __acl__(self):
		cce = self.context
		non_public = find_interface(cce, INonPublicCourseInstance, strict=False)
		if non_public:
			course_in_lineage = find_interface(cce, ICourseInstance, strict=False)
			if course_in_lineage is not None:
				# Inherit
				return ()
			# Ok, we must be non-public ourself. This is the legacy case.
			# Do we have a course instance?
			course = ICourseInstance(cce, None)
			if course is not None:
				acl = IACLProvider(course).__acl__
				acl.append(
					# Nobody can 'create' (enroll)
					# Nobody else can view it either
					ace_denying( IPrincipal(EVERYONE_GROUP_NAME),
								 (ACT_CREATE, ACT_READ),
								 CourseCatalogEntryACLProvider ),
				)

				return acl

			# Hmm.
			return [ACE_DENY_ALL]

		acl = acl_from_aces(
			ace_allowing( IPrincipal(AUTHENTICATED_GROUP_NAME),
						  (ACT_CREATE, ACT_READ),
						  CourseCatalogEntryACLProvider)
		)
		return acl

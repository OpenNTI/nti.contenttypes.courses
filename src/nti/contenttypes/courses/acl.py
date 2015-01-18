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

from zope.security.interfaces import IPrincipal

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import EVERYONE_GROUP_NAME
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.interfaces import IACLProvider

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CREATE
from nti.dataserver.authorization_acl import ace_denying
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.utils.property import Lazy

from .interfaces import ES_PUBLIC
from .interfaces import ES_CREDIT
from .interfaces import ES_PURCHASED
from .interfaces import ICourseInstance
from .interfaces import ICourseEnrollments
from .interfaces import ICourseCatalogEntry
from .interfaces import INonPublicCourseInstance

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


	@property
	def __parent__(self):
		# See comments in nti.dataserver.authorization_acl:has_permission
		return self.context.__parent__

	@Lazy
	def __acl__(self):
		course = self.context
		sharing_scopes = course.SharingScopes
		sharing_scopes.initScopes()
		
		## chose permission scopes
		main_scopes = (sharing_scopes[ES_PUBLIC],)
		if INonPublicCourseInstance.providedBy(course):
			main_scopes = (sharing_scopes[ES_CREDIT], sharing_scopes[ES_PURCHASED])
		
		aces = [ace_allowing( IPrincipal(x), ACT_READ, CourseInstanceACLProvider)
				for x in main_scopes]
		
		aces.extend( ace_allowing( i, ACT_READ, CourseInstanceACLProvider )
					 for i in course.instructors)

		## JZ: 2015-01-11 Subinstance instructors get the same permissions 
		## as their students.
		for subinstance in course.SubInstances.values():
			aces.extend(ace_allowing( i, ACT_READ, CourseInstanceACLProvider )
						for i in subinstance.instructors)

		result = acl_from_aces( aces )
		return result
	
from nti.dataserver.traversal import find_interface

@component.adapter(ICourseCatalogEntry)
@interface.implementer(IACLProvider)
class CourseCatalogEntryACLProvider(object):
	"""
	Provides the ACL for course catalog entries.
	"""

	def __init__(self, context):
		self.context = context

	@property
	def __parent__(self):
		# See comments in nti.dataserver.authorization_acl:has_permission
		return self.context.__parent__

	@Lazy
	def __acl__(self):
		cce = self.context
		# catalog entries can be non-public children of public courses,
		# or public children of non-public courses.
		non_public = find_interface(cce, INonPublicCourseInstance, strict=False)

		if non_public:
			# Ok, was that us, or are we not non-public and our direct parent
			# is also not non-public?
			if 	INonPublicCourseInstance.providedBy(self.context) or \
				INonPublicCourseInstance.providedBy(self.__parent__):
				non_public = True
			else:
				# We don't directly provide it, neither does our parent, so
				# we actually want to be public and not inherit this.
				non_public = False

		if non_public:
			# Although it might be be nice to inherit from the non-public
			# course in our lineage, we actually need to be a bit stricter
			# than that...the course cannot forbid creation or do a deny-all
			# (?)
			course_in_lineage = find_interface(cce, ICourseInstance, strict=False)

			# Do we have a course instance? If it's not in our lineage its the legacy
			# case
			course = course_in_lineage or ICourseInstance(cce, None)
			if course is not None:
				acl = IACLProvider(course).__acl__
				# check if there are open enrollments. we still want to be able to give
				# them access to this course entry (e.g 2014 - chem of beer 100)
				if has_open_enrollments(course):
					# we only give them readaccess
					sharing_scopes = course.SharingScopes
					main_scope = sharing_scopes[ES_PUBLIC]
					acl = acl_from_aces(
						ace_allowing(IPrincipal(main_scope), ACT_READ,
									 CourseCatalogEntryACLProvider)
					)
				acl.append(
					# Nobody can 'create' (enroll)
					# Nobody else can view it either
					ace_denying( IPrincipal(AUTHENTICATED_GROUP_NAME),
								 (ACT_CREATE, ACT_READ),
								 CourseCatalogEntryACLProvider ),
				)
				acl.append(
					# use both everyone and authenticated for belt-and-suspenders
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

def has_open_enrollments(course):
	if course is not None:
		try:
			for record in ICourseEnrollments(course).iter_enrollments():
				if record.Scope == ES_PUBLIC:
					return True
		except StandardError:
			logger.exception("Cannot get course enrollments")
	return False

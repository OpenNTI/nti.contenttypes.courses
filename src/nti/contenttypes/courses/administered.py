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

from zope.intid.interfaces import IIntIds

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.principalrole import principalRoleManager

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import EDITOR
from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IUserAdministeredCourses
from nti.contenttypes.courses.interfaces import ICourseInstanceAdministrativeRole
from nti.contenttypes.courses.interfaces import IPrincipalAdministrativeRoleCatalog

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import AbstractInstanceWrapper

from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IGroupMember

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.site.site import get_component_hierarchy_names

@interface.implementer(IUserAdministeredCourses)
class IndexAdminCourses(object):

	def iter_admin(self, user):
		intids = component.getUtility(IIntIds)
		catalog = get_enrollment_catalog()
		sites = get_component_hierarchy_names()
		username = getattr(user, 'username', user)
		query = {
			IX_SITE:{'any_of': sites},
			IX_SCOPE: {'any_of':(INSTRUCTOR, EDITOR)},
			IX_USERNAME:{'any_of':(username,)},
		}
		for uid in catalog.apply(query) or ():
			context = intids.queryObject(uid)
			if ICourseInstance.providedBy(context):  # extra check
				yield context

@interface.implementer(IUserAdministeredCourses)
class IterableAdminCourses(object):

	def iter_admin(self, user):
		principal = IPrincipal(user)
		catalog = component.getUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			instance = ICourseInstance(entry)
			if		principal in instance.instructors \
				or	principal in get_course_editors(instance):
				yield instance

@interface.implementer(ICourseInstanceAdministrativeRole)
class CourseInstanceAdministrativeRole(SchemaConfigured,
									   AbstractInstanceWrapper):
	createDirectFieldProperties(ICourseInstanceAdministrativeRole,
								# Be flexible about what this is,
								# the LegacyCommunityInstance doesn't fully comply
								omit=('CourseInstance',))

	mime_type = mimeType = u"application/vnd.nextthought.courseware.courseinstanceadministrativerole" # legacy

	def __init__(self, CourseInstance=None, RoleName=None):
		# SchemaConfigured is not cooperative
		SchemaConfigured.__init__(self, RoleName=RoleName)
		AbstractInstanceWrapper.__init__(self, CourseInstance)

@component.adapter(IUser)
@interface.implementer(IPrincipalAdministrativeRoleCatalog)
class _DefaultPrincipalAdministrativeRoleCatalog(object):
	"""
	This catalog returns all courses the user is in the instructors list,
	or all courses if the user is a global content admin.
	"""

	def __init__(self, user):
		self.user = user

	def _is_admin(self):
		for _, adapter in component.getAdapters((self.user,), IGroupMember):
			if adapter.groups and ROLE_ADMIN in adapter.groups:
				return True
		return False

	def _is_content_admin(self):
		roles = principalRoleManager.getRolesForPrincipal(self.user.username)
		for role, access in roles or ():
			if role == ROLE_CONTENT_ADMIN.id and access == Allow:
				return True
		return False

	def _iter_all_courses(self):
		# We do not filter based on enrollment or anything else.
		# This will probably move to its own workspace eventually.
		is_admin = self._is_admin()
		catalog = component.queryUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			course = ICourseInstance(entry, None)
			if		 course is not None \
				and not ILegacyCourseInstance.providedBy(course) \
				and (   is_admin
					 or	has_permission(ACT_CONTENT_EDIT, entry, self.user)):
				yield course

	def _iter_admin_courses(self):
		util = component.getUtility(IUserAdministeredCourses)
		for context in util.iter_admin(self.user):
			yield context

	def _get_course_iterator(self):
		result = self._iter_admin_courses
		if self._is_content_admin() or self._is_admin():
			result = self._iter_all_courses
		return result

	def iter_administrations(self):
		for course in self._get_course_iterator()():
			roles = IPrincipalRoleMap(course)
			# For now, we're including editors in the administered
			# workspace.
			if roles.getSetting(RID_INSTRUCTOR, self.user.id) is Allow:
				role = u'instructor'
			elif roles.getSetting(RID_TA, self.user.id) is Allow:
				role = u'teaching assistant'
			else:
				role = u'editor'
			yield CourseInstanceAdministrativeRole(RoleName=role, CourseInstance=course)
	iter_enrollments = iter_administrations  # for convenience

	def count_administrations(self):
		result = tuple(self._iter_admin_courses())
		return len(result)

	count_enrollments = count_administrations

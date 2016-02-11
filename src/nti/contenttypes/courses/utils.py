#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from itertools import chain

from zope import component

from zope.catalog.interfaces import ICatalog

from zope.component.hooks import getSite

from zope.component.interfaces import ComponentLookupError

from zope.intid.interfaces import IIntIds

from zope.location import LocationIterator

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import IX_COURSE
from nti.contenttypes.courses.index import IndexRecord
from nti.contenttypes.courses.index import ENROLLMENT_CATALOG_NAME

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import EDITOR
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo

from nti.contenttypes.courses.vendorinfo import VENDOR_INFO_KEY

from nti.dataserver.users import User

def get_enrollment_catalog():
	return component.queryUtility(ICatalog, name=ENROLLMENT_CATALOG_NAME)

def get_course_vendor_info(context, create=True):
	result = None
	course = ICourseInstance(context, None)
	if create:
		result = ICourseInstanceVendorInfo(context, None)
	elif course is not None:
		try:
			annotations = course.__annotations__
			result = annotations.get(VENDOR_INFO_KEY, None)
		except AttributeError:
			pass
	return result

def unindex_course_roles(context, catalog=None):
	course = ICourseInstance(context, None)
	entry = ICourseCatalogEntry(course, None)
	catalog = get_enrollment_catalog() if catalog is None else catalog
	if entry is not None:  # remove all instructors
		site = getSite().__name__
		query = { IX_SITE: {'any_of':(site,)},
				  IX_COURSE: {'any_of':(entry.ntiid,)},
				  IX_SCOPE : {'any_of':(INSTRUCTOR, EDITOR)}}
		for uid in catalog.apply(query) or ():
			catalog.unindex_doc(uid)

def _index_instructors(course, catalog, entry, doc_id):
	result = 0
	for instructor in course.instructors or ():
		principal = IPrincipal(instructor, None)
		if principal is None:
			continue
		pid = principal.id
		record = IndexRecord(pid, entry.ntiid, INSTRUCTOR)
		catalog.index_doc(doc_id, record)
		result += 1
	return result

def _index_editors(course, catalog, entry, doc_id):
	result = 0
	for editor in get_course_editors(course) or ():
		principal = IPrincipal(editor, None)
		if principal is None:
			continue
		pid = principal.id
		record = IndexRecord(pid, entry.ntiid, EDITOR)
		catalog.index_doc(doc_id, record)
		result += 1
	return result

def index_course_roles(context, catalog=None, intids=None):
	course = ICourseInstance(context, None)
	entry = ICourseCatalogEntry(context, None)
	if entry is None:
		return 0

	catalog = get_enrollment_catalog() if catalog is None else catalog
	intids = component.getUtility(IIntIds) if intids is None else intids
	doc_id = intids.queryId(course)
	if doc_id is None:
		return 0

	result = 0
	result += _index_instructors(course, catalog, entry, doc_id)
	result += _index_editors(course, catalog, entry, doc_id)
	return result

def get_parent_course(context):
	course = ICourseInstance(context, None)
	if ICourseSubInstance.providedBy(course):
		course = course.__parent__.__parent__
	return course

def get_course_subinstances(context):
	course = ICourseInstance(context, None)
	if course is not None and not ICourseSubInstance.providedBy(course):
		return tuple(course.SubInstances.values())
	return ()

def get_course_hierarchy(context):
	result = []
	parent = get_parent_course(context)
	if parent is not None:
		result.append(parent)
		result.extend(parent.SubInstances.values())
	return result

get_course_content_packages = get_course_packages # BWC

def is_there_an_open_enrollment(course, user):
	for instance in get_course_hierarchy(course):
		enrollments = ICourseEnrollments(instance)
		record = enrollments.get_enrollment_for_principal(user)
		if record is not None and record.Scope == ES_PUBLIC:
			return True
	return False

def get_enrollment_in_hierarchy(course, user):
	for instance in get_course_hierarchy(course):
		enrollments = ICourseEnrollments(instance)
		record = enrollments.get_enrollment_for_principal(user)
		if record is not None:
			return record
	return None
get_any_enrollment = get_enrollment_in_hierarchy

def drop_any_other_enrollments(context, user, ignore_existing=True):
	result = []
	main_course = ICourseInstance(context)
	main_entry = ICourseCatalogEntry(main_course)
	for instance in get_course_hierarchy(main_course):
		instance_entry = ICourseCatalogEntry(instance)
		if ignore_existing and main_entry.ntiid == instance_entry.ntiid:
			continue
		enrollments = ICourseEnrollments(instance)
		enrollment = enrollments.get_enrollment_for_principal(user)
		if enrollment is not None:
			enrollment_manager = ICourseEnrollmentManager(instance)
			enrollment_manager.drop(user)
			entry = ICourseCatalogEntry(instance, None)
			logger.warn("User %s dropped from course '%s' open enrollment", user,
						getattr(entry, 'ProviderUniqueID', None))
			result.append(instance)
	return result

def get_instructors_in_roles(roles, setting=Allow):
	result = set()
	instructors = chain(roles.getPrincipalsForRole(RID_TA) or (),
		  				roles.getPrincipalsForRole(RID_INSTRUCTOR) or ())
	for principal, stored in instructors:
		if stored == setting:
			pid = getattr(principal, 'id', str(principal))
			result.add(pid)
	return result

def get_course_editors(context, setting=Allow):
	result = []
	course = ICourseInstance(context, None)
	role_manager = IPrincipalRoleManager(course, None)
	if role_manager is not None:
		for prin, setting in role_manager.getPrincipalsForRole(RID_CONTENT_EDITOR):
			if setting is setting:
				try:
					user = User.get_user(prin)
					principal = IPrincipal(user, None)
				except (LookupError, TypeError):
					# lookuperror if we're not in a ds context,
					pass
				else:
					if principal is not None:
						result.append(principal)
	return result

def get_course_instructors(context, setting=Allow):
	course = ICourseInstance(context, None)
	roles = IPrincipalRoleMap(course, None)
	result = get_instructors_in_roles(roles, setting) if roles else ()
	return result

def is_course_instructor(context, user):
	result = False
	prin = IPrincipal(user, None)
	course = ICourseInstance(context, None)
	roles = IPrincipalRoleMap(course, None)
	if roles and prin:
		result = Allow in (roles.getSetting(RID_TA, prin.id),
						   roles.getSetting(RID_INSTRUCTOR, prin.id))
	return result

def course_locator(context):
	for x in LocationIterator(context):
		course = ICourseInstance(x, None)
		if course is not None:
			return course
	return None

def is_instructed_by_name(context, username):
	"""
	Checks if the context is within something instructed
	by the given principal id. The context will be searched
	for an ICourseInstance.

	If either the context or username is missing, returns
	a false value.
	"""

	if username is None or context is None:
		return False

	course = course_locator(context)
	roles = IPrincipalRoleMap(course, None)
	if roles:
		result = Allow in (roles.getSetting(RID_TA, username),
						   roles.getSetting(RID_INSTRUCTOR, username))
		return result
	return False

def is_course_editor(context, user):
	result = False
	prin = IPrincipal(user, None)
	course = ICourseInstance(context, None)
	roles = IPrincipalRoleManager(course, None)
	if roles and prin:
		result = (Allow == roles.getSetting(RID_CONTENT_EDITOR, prin.id))
	return result

def is_edited_by_name(context, username):
	"""
	Checks if the context is within something that can be edited
	by the given principal id. The context will be searched
	for an ICourseInstance.

	If either the context or username is missing, returns
	a false value.
	"""

	if username is None or context is None:
		return False

	course = course_locator(context)
	roles = IPrincipalRoleMap(course, None)
	if roles:
		result = (Allow == roles.getSetting(RID_CONTENT_EDITOR, username))
		return result
	return False

def is_instructed_or_edited_by_name(context, username):
	if username is None or context is None:
		return False

	course = course_locator(context)
	roles = IPrincipalRoleMap(course, None)
	if roles:
		result = Allow in (roles.getSetting(RID_TA, username),
						   roles.getSetting(RID_INSTRUCTOR, username),
						   roles.getSetting(RID_CONTENT_EDITOR, username))
		return result
	return False

def is_instructor_in_hierarchy(context, user):
	for instance in get_course_hierarchy(context):
		if is_course_instructor(instance, user):
			return True
	return False

def get_instructed_course_in_hierarchy(context, user):
	for instance in get_course_hierarchy(context):
		if is_course_instructor(instance, user):
			return instance
	return None

def is_course_instructor_or_editor(context, user):
	result = is_course_instructor(context, user) or is_course_editor(context, user)
	return result

def get_catalog_entry(ntiid, safe=True):
	try:
		catalog = component.getUtility(ICourseCatalog)
		entry = catalog.getCatalogEntry(ntiid) if ntiid else None
		return entry
	except (ComponentLookupError, KeyError) as e:
		if not safe:
			raise e
	return None

def get_enrollment_record(context, user):
	course = ICourseInstance(context, None)
	enrollments = ICourseEnrollments(course, None)
	record = enrollments.get_enrollment_for_principal(user) \
			 if user is not None and enrollments is not None else None
	return record

def get_enrollment_record_in_hierarchy(context, user):
	for instance in get_course_hierarchy(context):
		record = get_enrollment_record(instance, user)
		if record is not None:
			return record
	return None

def is_enrolled(context, user):
	record = get_enrollment_record(context, user)
	return record is not None

def is_enrolled_in_hierarchy(context, user):
	record = get_enrollment_record_in_hierarchy(context, user)
	return record is not None

def has_enrollments(user):
	for enrollments in component.subscribers((user,), IPrincipalEnrollments):
		if enrollments.count_enrollments():
			return True
	return False

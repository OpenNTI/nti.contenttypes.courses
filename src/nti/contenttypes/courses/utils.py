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

from zope.component.hooks import getSite
from zope.component.interfaces import ComponentLookupError

from zope.intid import IIntIds

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.dataserver.users import User

from .index import IX_SITE
from .index import IX_SCOPE
from .index import IX_COURSE
from .index import IndexRecord

from .interfaces import RID_TA
from .interfaces import EDITOR
from .interfaces import ES_PUBLIC
from .interfaces import INSTRUCTOR
from .interfaces import RID_INSTRUCTOR
from .interfaces import ICourseCatalog
from .interfaces import ICourseInstance
from .interfaces import RID_CONTENT_EDITOR
from .interfaces import ICourseEnrollments
from .interfaces import ICourseSubInstance
from .interfaces import ICourseCatalogEntry
from .interfaces import IPrincipalEnrollments
from .interfaces import ICourseEnrollmentManager

from . import get_enrollment_catalog

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

def get_course_packages(context):
	course = ICourseInstance(context, None)
	if course is not None:
		try:
			packs = course.ContentPackageBundle.ContentPackages
		except AttributeError:
			packs = (course.legacy_content_package,)
		return packs or ()
	return ()

def get_parent_course(context):
	course = ICourseInstance(context, None)
	if ICourseSubInstance.providedBy(course):
		course = course.__parent__.__parent__
	return course

def get_course_subinstances(context):
	course = ICourseInstance(context, None)
	if course is not None and not ICourseSubInstance.providedBy(course):
		return list(course.SubInstances.values())
	return ()

def get_course_hierarchy(context):
	result = []
	parent = get_parent_course(context)
	if parent is not None:
		result.append(parent)
		result.extend(parent.SubInstances.values())
	return result

def is_there_an_open_enrollment(course, user):
	main_course = get_parent_course(course)
	if main_course is not None:
		for instance in chain((main_course,), main_course.SubInstances.values()):
			enrollments = ICourseEnrollments(instance)
			record = enrollments.get_enrollment_for_principal(user)
			if record is not None and record.Scope == ES_PUBLIC:
				return True
	return False

def get_enrollment_in_hierarchy(course, user):
	main_course = get_parent_course(course)
	if main_course is not None:
		for instance in chain((main_course,), main_course.SubInstances.values()):
			enrollments = ICourseEnrollments(instance)
			record = enrollments.get_enrollment_for_principal(user)
			if record is not None:
				return record
	return None
get_any_enrollment = get_enrollment_in_hierarchy

def drop_any_other_enrollments(context, user, ignore_existing=True):
	course = ICourseInstance(context)
	entry = ICourseCatalogEntry(course)
	course_ntiid = entry.ntiid

	result = []
	main_course = get_parent_course(course)
	if main_course is not None:
		for instance in chain((main_course,) , main_course.SubInstances.values()):
			instance_entry = ICourseCatalogEntry(instance)
			if ignore_existing and course_ntiid == instance_entry.ntiid:
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

def is_course_editor(context, user):
	result = False
	prin = IPrincipal(user, None)
	course = ICourseInstance(context, None)
	roles = IPrincipalRoleMap(course, None)
	if roles and prin:
		result = (Allow == roles.getSetting(RID_CONTENT_EDITOR, prin.id))
	return result

def is_instructor_in_hierarchy(context, user):
	main_course = get_parent_course(context)
	if main_course is not None:
		for instance in chain((main_course,) , main_course.SubInstances.values()):
			if is_course_instructor(instance, user):
				return True
	return False

def get_instructed_course_in_hierarchy(context, user):
	main_course = get_parent_course(context)
	if main_course is not None:
		for instance in chain((main_course,) , main_course.SubInstances.values()):
			if is_course_instructor(instance, user):
				return instance
	return None

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
	main_course = get_parent_course(context)
	if main_course is not None:
		for instance in chain((main_course,) , main_course.SubInstances.values()):
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

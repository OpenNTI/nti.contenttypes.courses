#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import namedtuple

from zope import interface

from zope.catalog.interfaces import ICatalog

from zope.component.hooks import getSite

from zope.deprecation import deprecated

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.common.string import to_unicode

from nti.contenttypes.courses.common import get_course_site
from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseKeywords
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.zope_catalog.catalog import Catalog

from nti.zope_catalog.index import AttributeSetIndex
from nti.zope_catalog.index import AttributeKeywordIndex
from nti.zope_catalog.index import SetIndex as RawSetIndex
from nti.zope_catalog.index import AttributeValueIndex as ValueIndex

# Deprecations

deprecated('ValidatingUsernameID', 'Use lastest index implementation')
class ValidatingUsernameID(object):

	def __init__(self, *args, **kwargs):
		pass

deprecated('SiteIndex', 'Replaced with SingleSiteIndex')
class SiteIndex(RawSetIndex):
	pass

# Utilities

class KeepSetIndex(RawSetIndex):

	empty_set = set()

	def to_iterable(self, value):
		return value

	def index_doc(self, doc_id, value):
		value = {v for v in self.to_iterable(value) if v is not None}
		old = self.documents_to_values.get(doc_id) or self.empty_set
		if value.difference(old):
			value.update(old)
			result = super(KeepSetIndex, self).index_doc(doc_id, value)
			return result

	def remove(self, doc_id, value):
		old = set(self.documents_to_values.get(doc_id) or ())
		if not old:
			return
		for v in self.to_iterable(value):
			old.discard(v)
		if old:
			super(KeepSetIndex, self).index_doc(doc_id, old)
		else:
			super(KeepSetIndex, self).unindex_doc(doc_id)

# Enrollment catalog

IndexRecord = namedtuple('IndexRecord', 'username ntiid Scope')

ENROLLMENT_CATALOG_NAME = 'nti.dataserver.++etc++enrollment-catalog'

IX_SITE = 'site'
IX_SCOPE = 'scope'
IX_ENTRY = IX_COURSE = 'course'
IX_USERNAME = IX_STUDENT = IX_INSTRUCTOR = 'username'

class ValidatingSiteName(object):

	__slots__ = (b'site',)

	def __init__(self, obj, default=None):
		if isinstance(obj, IndexRecord):
			self.site = unicode(getSite().__name__)
		elif ICourseInstanceEnrollmentRecord.providedBy(obj):
			course = ICourseInstance(obj, None)
			self.site = get_course_site(course) or getSite().__name__

	def __reduce__(self):
		raise TypeError()

class SingleSiteIndex(ValueIndex):
	default_field_name = 'site'
	default_interface = ValidatingSiteName

class UsernameIndex(KeepSetIndex):

	def to_iterable(self, value):
		if isinstance(value, IndexRecord):
			result = (to_unicode(value.username),)
		elif ICourseInstanceEnrollmentRecord.providedBy(value):
			result = (value.Principal.id,) if value.Principal is not None else ()
		elif isinstance(value, (list, tuple, set)):
			result = value
		else:
			result = ()
		return result

class ValidatingScope(object):

	__slots__ = (b'scope',)

	def __init__(self, obj, default=None):
		if isinstance(obj, IndexRecord):
			self.scope = to_unicode(obj.Scope)
		elif ICourseInstanceEnrollmentRecord.providedBy(obj):
			self.scope = obj.Scope

	def __reduce__(self):
		raise TypeError()

class ScopeIndex(ValueIndex):
	default_field_name = 'scope'
	default_interface = ValidatingScope

class ValidatingCatalogEntryID(object):

	__slots__ = (b'ntiid',)

	def __init__(self, obj, default=None):
		if isinstance(obj, IndexRecord):
			self.ntiid = to_unicode(obj.ntiid)
		elif ICourseInstanceEnrollmentRecord.providedBy(obj):
			entry = ICourseCatalogEntry(obj.CourseInstance, None)
			if entry is not None:
				self.ntiid = unicode(entry.ntiid)

	def __reduce__(self):
		raise TypeError()

class CatalogEntryIDIndex(ValueIndex):
	default_field_name = 'ntiid'
	default_interface = ValidatingCatalogEntryID

@interface.implementer(ICatalog)
class EnrollmentCatalog(Catalog):
	pass

def install_enrollment_catalog(site_manager_container, intids=None):
	lsm = site_manager_container.getSiteManager()
	intids = lsm.getUtility(IIntIds) if intids is None else intids
	catalog = lsm.queryUtility(ICatalog, name=ENROLLMENT_CATALOG_NAME)
	if catalog is not None:
		return catalog

	catalog = EnrollmentCatalog(family=intids.family)
	locate(catalog, site_manager_container, ENROLLMENT_CATALOG_NAME)
	intids.register(catalog)
	lsm.registerUtility(catalog, provided=ICatalog, name=ENROLLMENT_CATALOG_NAME)

	for name, clazz in ((IX_SCOPE, ScopeIndex),
						(IX_SITE, SingleSiteIndex),
						(IX_USERNAME, UsernameIndex),
						(IX_ENTRY, CatalogEntryIDIndex)):
		index = clazz(family=intids.family)
		intids.register(index)
		locate(index, catalog, name)
		catalog[name] = index
	return catalog

# Courses catalog

IX_PACKAGES = 'packages'
IX_KEYWORDS = 'keywords'
COURSES_CATALOG_NAME = 'nti.dataserver.++etc++courses-catalog'

class ValidatingCourseSiteName(object):

	__slots__ = (b'site',)

	def __init__(self, obj, default=None):
		if ICourseInstance.providedBy(obj):
			self.site = get_course_site(obj) or u''

	def __reduce__(self):
		raise TypeError()

class CourseSiteIndex(ValueIndex):
	default_field_name = 'site'
	default_interface = ValidatingCourseSiteName

class ValidatingCourseCatalogEntry(object):

	__slots__ = (b'ntiid',)

	def __init__(self, obj, default=None):
		if ICourseInstance.providedBy(obj):
			entry = ICourseCatalogEntry(obj, None)
			self.ntiid = getattr(entry, 'ntiid', None)

	def __reduce__(self):
		raise TypeError()

class CourseCatalogEntryIndex(ValueIndex):
	default_field_name = 'ntiid'
	default_interface = ValidatingCourseCatalogEntry

class ValidatingCoursePackages(object):

	__slots__ = (b'packages',)

	def __init__(self, obj, default=None):
		if ICourseInstance.providedBy(obj):
			packs = get_course_packages(obj)
			self.packages = {getattr(x, 'ntiid', None) for x in packs}
			self.packages.discard(None)

	def __reduce__(self):
		raise TypeError()

class CoursePackagesIndex(AttributeSetIndex):
	default_field_name = 'packages'
	default_interface = ValidatingCoursePackages

class CourseKeywordsIndex(AttributeKeywordIndex):
	default_field_name = 'keywords'
	default_interface = ICourseKeywords

@interface.implementer(ICatalog)
class CoursesCatalog(Catalog):
	pass

def install_courses_catalog(site_manager_container, intids=None):
	lsm = site_manager_container.getSiteManager()
	intids = lsm.getUtility(IIntIds) if intids is None else intids
	catalog = lsm.queryUtility(ICatalog, name=COURSES_CATALOG_NAME)
	if catalog is not None:
		return catalog

	catalog = CoursesCatalog(family=intids.family)
	locate(catalog, site_manager_container, COURSES_CATALOG_NAME)
	intids.register(catalog)
	lsm.registerUtility(catalog, provided=ICatalog, name=COURSES_CATALOG_NAME)

	for name, clazz in ((IX_SITE, CourseSiteIndex),
						(IX_PACKAGES, CoursePackagesIndex),
						(IX_KEYWORDS, CourseKeywordsIndex),
						(IX_ENTRY, CourseCatalogEntryIndex)):
		index = clazz(family=intids.family)
		intids.register(index)
		locate(index, catalog, name)
		catalog[name] = index
	return catalog

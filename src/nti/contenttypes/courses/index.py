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

from zope.intid import IIntIds

from zope.location import locate

from nti.common.string import safestr

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

from nti.zope_catalog.catalog import Catalog
from nti.zope_catalog.index import SetIndex as RawSetIndex
from nti.zope_catalog.index import AttributeValueIndex as ValueIndex

# utilities

class KeepSetIndex(RawSetIndex):

	empty_set = set()

	def to_iterable(self, value):
		return value

	def index_doc(self, doc_id, value):
		value = {v for v in self.to_iterable(value) if v is not None}
		old = self.documents_to_values.get(doc_id) or self.empty_set
		if value.difference(old):
			value.update(old or ())
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

# enrollment catalog

deprecated('ValidatingUsernameID', 'Use lastest index implementation')
class ValidatingUsernameID(object):

	def __init__(self, *args, **kwargs):
		pass

deprecated('SiteIndex', 'Replaced with SingleSiteIndex')
class SiteIndex(RawSetIndex):
	pass

IndexRecord = namedtuple('IndexRecord', 'username ntiid Scope')

ENROLLMENT_CATALOG_NAME = 'nti.dataserver.++etc++enrollment-catalog'

IX_SITE = 'site'
IX_SCOPE = 'scope'
IX_ENTRY = IX_COURSE = 'course'
IX_USERNAME = IX_STUDENT = IX_INSTRUCTOR = 'username'

class ValidatingSiteName(object):

	__slots__ = (b'site',)

	def __init__(self, obj, default=None):
		if 	isinstance(obj, IndexRecord) or \
			ICourseInstanceEnrollmentRecord.providedBy(obj):
			self.site = unicode(getSite().__name__)
		elif IHostPolicyFolder.providedBy(obj):
			self.site = unicode(obj.__name__)
		elif ICourseInstance.providedBy(obj):
			folder = find_interface(obj, IHostPolicyFolder, strict=False)
			self.site = unicode(getattr(folder,'__name__', None) or u'')

	def __reduce__(self):
		raise TypeError()

class SingleSiteIndex(ValueIndex):
	default_field_name = 'site'
	default_interface = ValidatingSiteName

class UsernameIndex(KeepSetIndex):

	def to_iterable(self, value):
		if isinstance(value, IndexRecord):
			result = (safestr(value.username),)
		elif ICourseInstanceEnrollmentRecord.providedBy(value):
			result = (value.Principal.id,) if value.Principal is not None else ()
		else:
			result = ()
		return result

class ValidatingScope(object):

	__slots__ = (b'scope',)

	def __init__(self, obj, default=None):
		if isinstance(obj, IndexRecord):
			self.scope = safestr(obj.Scope)
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
			self.ntiid = safestr(obj.ntiid)
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
	if intids is None:
		intids = lsm.getUtility(IIntIds)

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

# course catalog

COURSE_CATALOG_NAME = 'nti.dataserver.++etc++course-catalog'

class CourseSiteIndex(SingleSiteIndex):
	pass

@interface.implementer(ICatalog)
class CourseCatalog(Catalog):
	pass

def install_course_catalog(site_manager_container, intids=None):
	lsm = site_manager_container.getSiteManager()
	if intids is None:
		intids = lsm.getUtility(IIntIds)

	catalog = lsm.queryUtility(ICatalog, name=COURSE_CATALOG_NAME)
	if catalog is not None:
		return catalog

	catalog = CourseCatalog(family=intids.family)
	locate(catalog, site_manager_container, COURSE_CATALOG_NAME)
	intids.register(catalog)
	lsm.registerUtility(catalog, provided=ICatalog, name=COURSE_CATALOG_NAME)

	for name, clazz in ((IX_SITE, CourseSiteIndex),):
		index = clazz(family=intids.family)
		intids.register(index)
		locate(index, catalog, name)
		catalog[name] = index
	return catalog

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

from zope.deprecation import deprecated

from zope.location import locate

from zc.intid import IIntIds

from nti.common.string import safestr

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.site.interfaces import IHostPolicyFolder
from nti.site.site import get_component_hierarchy_names

from nti.zope_catalog.catalog import Catalog
from nti.zope_catalog.index import SetIndex as RawSetIndex
from nti.zope_catalog.index import AttributeValueIndex as ValueIndex

from .interfaces import ICourseInstanceEnrollmentRecord

CATALOG_NAME = 'nti.dataserver.++etc++enrollment-catalog'

IX_SITE = 'site'
IX_SCOPE = 'scope'
IX_ENTRY = IX_COURSE = 'course'
IX_USERNAME = IX_STUDENT = IX_INSTRUCTOR = 'username'

IndexRecord = namedtuple('IndexRecord', 'username ntiid Scope')

deprecated('ValidatingUsernameID', 'Use lastest index implementation')
class ValidatingUsernameID(object):

	def __init__(self, *args, **kwargs):
		pass
	
class KeepSetIndex(RawSetIndex):

	empty_set = set()

	def to_iterable(self, value):
		return value

	def index_doc(self, doc_id, value):
		value = {v for v in self.to_iterable(value) if v is not None}
		old = self.documents_to_values.get(doc_id) or self.empty_set
		if value.difference(old):
			value.update(old or ())
			result = super(UsernameIndex, self).index_doc(doc_id, value)
			return result

	def remove(self, doc_id, value):
		old = set(self.documents_to_values.get(doc_id) or ())
		if not old:
			return
		for v in self.to_iterable(value):
			old.discard(v)
		if old:
			super(UsernameIndex, self).index_doc(doc_id, old)
		else:
			super(UsernameIndex, self).unindex_doc(doc_id)

class SiteIndex(KeepSetIndex):

	def to_iterable(self, value=None):
		value = value if IHostPolicyFolder.providedBy(value) else None
		return get_component_hierarchy_names(value)
	
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

	catalog = lsm.queryUtility(ICatalog, name=CATALOG_NAME)
	if catalog is not None:
		return catalog

	catalog = EnrollmentCatalog(family=intids.family)
	locate(catalog, site_manager_container, CATALOG_NAME)
	intids.register(catalog)
	lsm.registerUtility(catalog, provided=ICatalog, name=CATALOG_NAME)

	for name, clazz in ((IX_SITE, SiteIndex),
						(IX_SCOPE, ScopeIndex),
						(IX_USERNAME, UsernameIndex),
						(IX_ENTRY, CatalogEntryIDIndex)):
		index = clazz(family=intids.family)
		intids.register(index)
		locate(index, catalog, name)
		catalog[name] = index
	return catalog

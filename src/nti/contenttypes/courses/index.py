#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope import interface

from zope.catalog.interfaces import ICatalog
from zope.catalog.interfaces import ICatalogIndex

from zope.location import locate

from zc.intid import IIntIds

from nti.common.string import safestr

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.zope_catalog.catalog import Catalog
from nti.zope_catalog.index import AttributeValueIndex as ValueIndex

from .interfaces import ICourseInstanceEnrollmentRecord

CATALOG_NAME = 'nti.dataserver.++etc++enrollment-catalog'

IX_SCOPE = 'scope'
IX_ENTRY = IX_COURSE = 'course'
IX_STUDENT = IX_USERNAME = 'username'

class ValidatingUsernameID(object):

	__slots__ = (b'username',)

	def __init__(self, obj, default=None):
		if isinstance(obj, six.string_types):
			self.username = safestr(obj)
		elif ICourseInstanceEnrollmentRecord.providedBy(obj):
			self.username = obj.Principal.id

	def __reduce__(self):
		raise TypeError()

class UsernameIndex(ValueIndex):
	default_field_name = 'username'
	default_interface = ValidatingUsernameID

class ValidatingScope(object):

	__slots__ = (b'scope',)

	def __init__(self, obj, default=None):
		if isinstance(obj, six.string_types):
			self.scope = safestr(obj)
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
		if isinstance(obj, six.string_types):
			self.ntiid = safestr(obj)
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

	for name, clazz in ((IX_SCOPE, ScopeIndex),
						(IX_USERNAME, UsernameIndex),
						(IX_ENTRY, CatalogEntryIDIndex)):
		index = clazz(family=intids.family)
		assert ICatalogIndex.providedBy(index)
		intids.register(index)
		locate(index, catalog, name)
		catalog[name] = index
	return catalog

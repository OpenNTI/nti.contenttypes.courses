#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 19

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import ScopeSetIndex
from nti.contenttypes.courses.index import install_enrollment_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import index_course_roles

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

@interface.implementer(IDataserver)
class MockDataserver(object):

	root = None

	def get_by_oid(self, oid, ignore_creator=False):
		resolver = component.queryUtility(IOIDResolver)
		if resolver is None:
			logger.warn("Using dataserver without a proper ISiteManager configuration.")
		else:
			return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
		return None

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = ds_folder
	component.provideUtility(mock_ds, IDataserver)

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"
		lsm = ds_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		index_catalog = install_enrollment_catalog(ds_folder, intids)
		old_index = index_catalog[IX_SCOPE]
		if not isinstance(old_index, ScopeSetIndex):
			del index_catalog[IX_SCOPE]  # remove intid

			new_index = ScopeSetIndex(family=intids.family)
			intids.register(new_index)
			locate(new_index, index_catalog, IX_SCOPE)
			index_catalog[IX_SCOPE] = new_index

			# index enollment records
			for doc_id in old_index.ids():
				value = intids.queryObject(doc_id)
				new_index.index_doc(doc_id, value)

			seen = set()
			for site in get_all_host_sites():
				with current_site(site):
					course_catalog = component.queryUtility(ICourseCatalog)
					if course_catalog is None or course_catalog.isEmpty():
						continue
					for entry in course_catalog.iterCatalogEntries():
						course = ICourseInstance(entry, None)
						if course is None or entry.ntiid in seen:
							continue
						seen.add(entry.ntiid)
						index_course_roles(course, index_catalog, intids)

			# clear and ground
			old_index.clear()
			old_index.__parent__ = None

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 19 by modifying the scope index
	"""
	do_evolve(context, generation)

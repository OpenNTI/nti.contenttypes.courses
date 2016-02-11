#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 16

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.index import install_courses_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

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

def _index_courses(site, index, intids):
	catalog = component.queryUtility(ICourseCatalog)
	if catalog is None or catalog.isEmpty():
		return
	for entry in catalog.iterCatalogEntries():
		course = ICourseInstance(entry)
		doc_id = intids.queryId(course)
		if doc_id is not None:
			index.index_doc(doc_id, course)

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
		catalog = install_courses_catalog(ds_folder, intids)

		sites = ds_folder['++etc++hostsites']
		for site in sites.values():
			with current_site(site):
				_index_courses(site, catalog, intids)

	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 16 by installing the courses catalog
	"""
	do_evolve(context, generation)

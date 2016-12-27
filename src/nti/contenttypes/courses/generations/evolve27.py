#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 27

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

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

def _fix_lineage(seen, catalog):
	for entry in catalog.iterCatalogEntries():
		if entry.ntiid in seen:
			continue
		seen.add(entry.ntiid)
		course = ICourseInstance(entry, None)
		if course is not None:
			discussions = course.Discussions
			if discussions.__parent__ is not course or discussions.__parent__ is None:
				logger.warn("Fixing discussions lineage for %s", entry.ntiid)
				discussions.__parent__ = course

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = ds_folder
	component.provideUtility(mock_ds, IDataserver)

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"
		seen = set()
		for site in get_all_host_sites():
			with current_site(site):
				course_catalog = component.queryUtility(ICourseCatalog)
				if course_catalog is not None and not course_catalog.isEmpty():
					_fix_lineage(seen, course_catalog)

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 27 by fixing discussions lineage.
	"""
	do_evolve(context, generation)

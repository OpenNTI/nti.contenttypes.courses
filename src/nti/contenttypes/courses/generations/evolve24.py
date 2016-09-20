#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 24

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.component.interfaces import ISite

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

def reset_site_managers(catalog):
	for entry in catalog.iterCatalogEntries():
		course = ICourseInstance(entry, None)
		if course is not None and getattr(course, '_sm', None) is not None:
			course._sm = None
			if ISite.providedBy(course):
				interface.noLongerProvides(course, ISite)
			logger.info("Sitemanager for %s was reset", entry.ntiid)

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = ds_folder
	component.provideUtility(mock_ds, IDataserver)

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		for site in get_all_host_sites():
			with current_site(site):
				catalog = component.queryUtility(ICourseCatalog)
				if catalog is not None:
					reset_site_managers(catalog)

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 24 by reseting the courses site managers
	"""
	do_evolve(context, generation)

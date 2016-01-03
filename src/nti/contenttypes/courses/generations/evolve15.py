#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 15

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.coremetadata.interfaces import IRecordable

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

def load_library():
	library = component.queryUtility(IContentPackageLibrary)
	if library is not None:
		library.syncContentPackages()

def _is_locked(obj):
	# Exclude locked objects (user created).
	return IRecordable.providedBy(obj) and obj.locked

def _publish( obj ):
	if not _is_locked( obj ):
		obj.publish()

def _handle_node( node ):
	_publish( node )
	publish_count = 1
	for child_node in node.values():
		publish_count += _handle_node( child_node )
	return publish_count

def _publish_catalog_objects( site ):
	catalog = component.queryUtility(ICourseCatalog)
	if catalog is None:
		return
	for entry in catalog.iterCatalogEntries():
		course = ICourseInstance( entry )
		if ILegacyCourseInstance.providedBy( course ):
			publish_count = _handle_node( course.Outline )
			logger.info( '[%s] Published %s nodes in %s', site.__name__,
						publish_count, entry.ntiid )

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = ds_folder
	component.provideUtility(mock_ds, IDataserver)

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		load_library()
		sites = ds_folder['++etc++hostsites']
		for site in sites.values():
			with current_site(site):
				_publish_catalog_objects( site )

	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 15 by publishing legacy course nodes.
	"""
	do_evolve(context, generation)

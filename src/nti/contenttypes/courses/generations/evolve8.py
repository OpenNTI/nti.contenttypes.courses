#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 8.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 8

from zope import component
from zope import interface

from zope.component.hooks import setHooks
from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from ZODB.POSException import POSError

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.index import IndexRecord
from nti.contenttypes.courses.index import install_enrollment_catalog

from nti.contenttypes.courses.interfaces import INSTRUCTOR
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseCatalogEntry

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

def _index_course_instructors(entry, course, catalog, intids):
	doc_id = intids.queryId(course)
	if doc_id is None:
		return 0

	result = 0
	for instructor in entry.Instructors or ():
		pid = instructor.username
		record = IndexRecord(pid, entry.ntiid, INSTRUCTOR)
		catalog.index_doc(doc_id, record)
		result += 1
	return result

def do_reindex(sites, catalog, intids):
	total = 0
	seen = set()
	for site in sites.values():
		with current_site(site):
			course_catalog = component.getUtility(ICourseCatalog)
			for entry in course_catalog.iterCatalogEntries():
				if entry.ntiid in seen or not ILegacyCourseCatalogEntry.providedBy(entry):
					continue
				seen.add(entry.ntiid)
				course = ICourseInstance(entry, None)
				if course is None:
					continue

				total += _index_course_instructors(entry, course, catalog, intids)

				# index enrollment records
				enrollments = ICourseEnrollments(course, None)
				if not enrollments:
					continue
				for e in enrollments.iter_enrollments():
					uid = intids.queryId(e)
					if uid is not None:
						try:
							catalog.index_doc(uid, e)
							total += 1
						except (TypeError, POSError):
							pass
	return total

def do_evolve(context, generation=generation):
	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = dataserver_folder
	component.provideUtility(mock_ds, IDataserver)

	with current_site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		load_library()

		lsm = dataserver_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		sites = dataserver_folder['++etc++hostsites']
		catalog = install_enrollment_catalog(dataserver_folder)

		do_reindex(sites, catalog, intids)
	
	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)

def evolve(context):
	"""
	Evolve to generation 8 by indexing all enrollment records for legacy courses
	"""
	do_evolve(context, generation)

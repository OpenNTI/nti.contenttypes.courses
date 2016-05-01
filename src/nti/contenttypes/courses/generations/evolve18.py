#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 18

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.contenttypes.courses.index import IX_ENTRY
from nti.contenttypes.courses.index import IX_KEYWORDS
from nti.contenttypes.courses.index import CourseKeywordsIndex
from nti.contenttypes.courses.index import install_courses_catalog

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
		if IX_KEYWORDS not in catalog:
			kw_index = CourseKeywordsIndex(family=intids.family)
			intids.register(kw_index)
			locate(kw_index, catalog, IX_KEYWORDS)
			catalog[IX_KEYWORDS] = kw_index
			# index keywords
			for doc_id in catalog[IX_ENTRY].ids():
				value = intids.queryObject(doc_id)
				if ICourseInstance.providedBy(value):
					kw_index.index_doc(doc_id, value)

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 18 by installing the course keyword index
	"""
	do_evolve(context, generation)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 17

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.index import IX_SITE 
from nti.contenttypes.courses.index import install_enrollment_catalog

from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.interfaces import IHostPolicyFolder

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
		catalog = install_enrollment_catalog(ds_folder, intids)
		index = catalog[IX_SITE]
		for doc_id in tuple(index.ids()): # mutating
			value = intids.queryObject(doc_id)
			if IHostPolicyFolder.providedBy(value):
				catalog.unindex_doc(doc_id) # remove crud
			elif ICourseInstanceEnrollmentRecord.providedBy(value):
				index.index_doc(doc_id, value)

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 17 by reindexing the sites for the enrollment catalog
	"""
	do_evolve(context, generation)

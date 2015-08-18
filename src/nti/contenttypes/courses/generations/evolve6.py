#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 6.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 6

from zope import component
from zope import interface

from zope.component.hooks import site, setHooks

from zope.intid import IIntIds

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from ..index import IX_USERNAME
from ..index import UsernameIndex
from ..index import install_enrollment_catalog

from .evolve4 import do_reindex

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

	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = dataserver_folder
	component.provideUtility(mock_ds, IDataserver)

	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = dataserver_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		catalog = install_enrollment_catalog(dataserver_folder)
	
		# remove old index
		index = catalog[IX_USERNAME]
		index.clear()
		intids.unregister(index)
		index.__name__ = None
		index.__parent__ = None
		del catalog[IX_USERNAME]
			
		# recreate new index
		index = catalog[IX_USERNAME] = UsernameIndex(family=intids.family)
		intids.register(index)
		index.__parent__ = catalog
		index.__name__ = IX_USERNAME
		
		sites = dataserver_folder['++etc++hostsites']
		total = do_reindex(sites, catalog, intids)
	
		logger.info('contenttypes.courses evolution %s done; %s object(s) indexed',
				generation, total)

def evolve(context):
	"""
	Evolve to generation 6 by indexing all enrollment records with the correct index
	"""
	do_evolve(context, generation)

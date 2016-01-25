#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 7.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 7

from zope import component

from zope.component.hooks import site, setHooks

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import SiteIndex
from nti.contenttypes.courses.index import install_enrollment_catalog

from .evolve4 import do_reindex
	
def do_evolve(context, generation=generation):

	setHooks()
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']

	with site(dataserver_folder):
		assert	component.getSiteManager() == dataserver_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = dataserver_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		catalog = install_enrollment_catalog(dataserver_folder)
		
		# recreate new index
		index = SiteIndex(family=intids.family)
		intids.register(index)
		index.__parent__ = catalog
		index.__name__ = IX_SITE
		catalog._setitemf(IX_SITE, index)

		sites = dataserver_folder['++etc++hostsites']
		total = do_reindex(sites, catalog, intids)
	
		logger.info('contenttypes.courses evolution %s done; %s object(s) indexed',
				generation, total)

def evolve(context):
	"""
	Evolve to generation 6 by indexing all enrollment records with the site index
	"""
	do_evolve(context, generation)

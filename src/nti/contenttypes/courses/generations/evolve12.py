#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 12

from zope import component

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import SingleSiteIndex
from nti.contenttypes.courses.index import install_enrollment_catalog

from nti.site.hostpolicy import get_all_host_sites

def do_evolve(context):
	setHooks()
	conn = context.connection
	root = conn.root()
	ds_folder = root['nti.dataserver']

	with site(ds_folder):
		assert  component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = ds_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		
		catalog = install_enrollment_catalog(ds_folder, intids)
		old_idx = catalog[IX_SITE]
		if isinstance(old_idx, SingleSiteIndex): # just in case
			return
		else:
			intids.unregister(old_idx)
			del catalog[IX_SITE]

		# recreate
		new_idx = SingleSiteIndex(family=catalog.family)
		intids.register(new_idx)
		locate(new_idx, catalog, IX_SITE)
		catalog[IX_SITE] = new_idx
		
		all_sites = get_all_host_sites()
		map_sites = {s.__name__:s for s in all_sites}
		idx_sites = {s.__name__:idx for idx, s in enumerate(all_sites)}
		
		for doc_id, names in old_idx.documents_to_values.items():
			if not names:
				continue
			if len(names) == 1:
				name = names.__iter__().next()
			else:
				data = sorted([(idx_sites.get(n),n) for n in names])
				name = data[0][1]
	
			reference = map_sites.get(name)
			new_idx.index_doc(doc_id, reference)

		old_idx.clear()
		logger.info('contenttypes.courses evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to gen 12 by updating site index in the enrollment catalog
	"""
	do_evolve(context)

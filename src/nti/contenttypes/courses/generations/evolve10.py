#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 10

from zope import component

from zope.component.hooks import site as current_site

from zope.intid import IIntIds

from nti.site.utils import unregisterUtility
from nti.site.hostpolicy import get_all_host_sites

from ..interfaces import iface_of_node

from ..interfaces import ICourseOutlineNode

def unregister(registry, name, provided):
	return unregisterUtility(registry=registry,
					  		 provided=provided,
					  		 name=name)

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	result = 0
	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		lsm = ds_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		for site in get_all_host_sites():
			with current_site(site):
				registry = component.getSiteManager()
				for _, obj in list(registry.getUtilitiesFor(ICourseOutlineNode)):
					ntiid = obj.ntiid
					if 	intids.queryId(obj) is None and \
						unregister(registry, ntiid, iface_of_node(obj)):
						result += 1

	logger.info('contenttypes.courses evolution %s done. %s node(s) unregistered',
				generation, result)

def evolve(context):
	"""
	Evolve to generation 10 by removing invalid nodes
	"""
	do_evolve(context, generation)

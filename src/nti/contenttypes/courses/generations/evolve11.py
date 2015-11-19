#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 11

from zope import component

from zope.component.hooks import site as current_site

from nti.contenttypes.courses.interfaces import ICourseOutlineNode

from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.coremetadata.interfaces import IRecordable

from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.site.utils import unregisterUtility
from nti.site.hostpolicy import get_all_host_sites

REGISTERED_TYPES = [ICourseOutlineNode, IPresentationAsset]

def unregister(registry, name, provided):
	return unregisterUtility(registry=registry,
					  		 provided=provided,
					  		 name=name)

def _is_locked(obj):
	# Exclude locked objects (user created).
	return IRecordable.providedBy(obj) and obj.locked

def _include(obj):
	# Exclude topics
	return not ITopic.providedBy(obj)

def _get_objects(registry):
	for registered_type in REGISTERED_TYPES:
		for _, obj in list(registry.getUtilitiesFor(registered_type)):
			if not _is_locked(obj) and _include(obj):
				yield obj

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	publish_count = 0
	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		for site in get_all_host_sites():
			with current_site(site):
				registry = component.getSiteManager()
				for obj in _get_objects(registry):
					obj.publish()
					publish_count += 1

	logger.info('contenttypes.courses evolution %s done. %s items published',
				generation, publish_count)

def evolve(context):
	"""
	Evolve to generation 11 by publishing content created nodes.
	"""
	do_evolve(context, generation)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 9.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 9

from zope import component

from zope.component.hooks import site as current_site

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility
from nti.site.hostpolicy import get_all_host_sites

from ..interfaces import NTI_COURSE_OUTLINE_NODE

from ..interfaces import ICourseCatalog
from ..interfaces import ICourseOutline
from ..interfaces import ICourseInstance
from ..interfaces import ICourseOutlineNode

from ..interfaces import iface_of_node

from ..legacy_catalog import ILegacyCourseCatalogEntry

def _outline_nodes(outline):
	result = []
	def _recur(node, idx=0):
		if not ICourseOutline.providedBy(node):
			result.append((node, idx))

		# parse children
		for n, child in enumerate(node.values()):
			_recur(child, n)

	_recur(outline)
	return result

def _replace(container, node):
	old_key = node.__name__
	data = container._data
	order = container._order

	# replace from ordered container
	data.pop(old_key, None)
	data[node.ntiid] = node
	idx = order.index(old_key)
	order[idx] = node.ntiid

	# set new name
	node.__name__ = node.ntiid

def unregister_nodes():
	result = 0
	sites = get_all_host_sites()
	for site in sites:
		with current_site(site):
			registry = component.getSiteManager()
			for name, _ in list(registry.getUtilitiesFor(ICourseOutlineNode)):
				result += 1
				unregisterUtility(registry=registry,
								  provided=ICourseOutlineNode,
								  name=name)
	logger.info('%s node(s) unregistered', result)
	return result

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']
	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"
				
		total = 0
		seen = set()
		unregister_nodes()
		sites = get_all_host_sites()
		for site in sites:
			with current_site(site):
				registry = component.getSiteManager()
				catalog = component.getUtility(ICourseCatalog)
				for entry in catalog.iterCatalogEntries():
					ntiid = entry.ntiid
					if ILegacyCourseCatalogEntry.providedBy(entry) or ntiid in seen:
						continue
					seen.add(ntiid)
					course = ICourseInstance(entry, None)
					if not course:
						continue
					for node, idx in _outline_nodes(course.Outline):
						parent = node.__parent__
						# generate new ntiid
						if parent == course.Outline:
							base = entry.ntiid
						else:
							base = parent.ntiid
						provider = get_provider(base)
						specific = get_specific(base) + '.%s' % idx
						ntiid = make_ntiid(nttype=NTI_COURSE_OUTLINE_NODE,
										   base=base,
										   provider=provider,
										   specific=specific)
						node.ntiid = ntiid
	
						# replace in container
						_replace(parent, node)
	
						# register
						registerUtility(registry,
										component=node,
										provided=iface_of_node(node),
										name=node.ntiid)
						total += 1

	logger.info('contenttypes.courses evolution %s done. %s node(s) updated',
				generation, total)

def evolve(context):
	"""
	Evolve to generation 9 by setting ntiids to outline nodes
	"""
	do_evolve(context, generation)

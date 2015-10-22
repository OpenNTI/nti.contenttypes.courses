#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 3.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 3

from zope import component

from zope.component.hooks import site as current_site

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific

from ..interfaces import NTI_COURSE_UNIT
from ..interfaces import NTI_COURSE_LESSON

from ..interfaces import ICourseCatalog
from ..interfaces import ICourseOutline
from ..interfaces import ICourseInstance

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

def do_evolve(context, generation=generation):
	conn = context.connection
	dataserver_folder = conn.root()['nti.dataserver']

	seen = ()
	sites = dataserver_folder['++etc++hostsites']
	for site in sites.values():
		with current_site(site):
			catalog = component.getUtility(ICourseCatalog)
			for entry in catalog.iterCatalogEntries():
				if ILegacyCourseCatalogEntry.providedBy(entry) or entry.ntiid in seen:
					continue
				seen.add(entry.ntiid)
				course = ICourseInstance(entry, None)
				if not course:
					continue
				base_specific = get_specific(entry.ntiid)
				for node, idx in _outline_nodes(course.Outline):
					if node.__parent__ == course.Outline:
						base = base_specific
						nttype = NTI_COURSE_UNIT
						specific = base_specific + ".%s" % idx
					else:
						base = node.__parent__.ntiid
						nttype = NTI_COURSE_LESSON
						specific = get_specific(base) + '.%s' % idx
					ntiid = make_ntiid(nttype=nttype, base=base, specific=specific)
					node.ntiid = ntiid

	logger.info('contenttypes.courses evolution %s done')

def evolve(context):
	"""
	Evolve to generation 9 by setting ntiids to outline nodes
	"""
	do_evolve(context, generation)


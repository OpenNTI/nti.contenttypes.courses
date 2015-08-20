#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 4.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 4

from zope import component

from zope.component.hooks import site as current_site

from ZODB.POSException import POSError

from ..interfaces import ICourseCatalog
from ..interfaces import ICourseInstance
from ..interfaces import ICourseEnrollments

from ..utils import index_course_instructors

def do_reindex(sites, catalog, intids):
	total = 0
	seen = set()
	for site in sites.values():
		with current_site(site):
			course_catalog = component.getUtility(ICourseCatalog)
			for entry in course_catalog.iterCatalogEntries():
				if entry.ntiid in seen:
					continue
				seen.add(entry.ntiid)
				course = ICourseInstance(entry, None)
				if not course:
					continue

				total += index_course_instructors(course, catalog=catalog, intids=intids)

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

def evolve(context):
	"""
	Evolve to generation 4 by indexing all enrollment records
	"""
	pass

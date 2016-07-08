#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 2.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 2

from zope import component

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.site.hostpolicy import get_all_host_sites

from nti.metadata import metadata_queue

def do_evolve(context, generation=generation):
	conn = context.connection
	dataserver_folder = conn.root()['nti.dataserver']

	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(IIntIds)

	total = 0
	for site in get_all_host_sites():
		with current_site(site):
			queue = metadata_queue()
			if queue is None:
				continue

			catalog = component.getUtility(ICourseCatalog)
			for entry in catalog.iterCatalogEntries():
				course = ICourseInstance(entry, None)
				if not course:
					continue
				enrollments = ICourseEnrollments(course, None)
				if not enrollments:
					continue
				for e in enrollments.iter_enrollments():
					uid = intids.queryId(e)
					if uid is not None:
						try:
							queue.add(uid)
							total += 1
						except TypeError:
							pass

	logger.info('Evolution %s done; %s object(s) put in queue',
				generation, total)

def evolve(context):
	pass

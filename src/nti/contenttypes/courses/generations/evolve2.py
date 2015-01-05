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

import zope.intid

from zope import component
from zope.component.hooks import site as current_site

from ..interfaces import ICourseCatalog
from ..interfaces import ICourseInstance
from ..interfaces import ICourseEnrollments

def do_evolve(context, generation=generation):
	try:
		from nti.metadata import metadata_queue
	except ImportError:
		return
	
	conn = context.connection
	dataserver_folder = conn.root()['nti.dataserver']
	
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(zope.intid.IIntIds)
	
	total = 0
	sites = dataserver_folder['++etc++hostsites']
	for site in sites.values():
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
							total +=1
						except TypeError:
							pass
						
	logger.info('contenttypes.courses evolution %s done; %s object(s) put in queue',
				generation, total)
			
def evolve(context):
	"""
	Evolve to generation 2 by putting all enrollment records in the metadata queue
	"""
	do_evolve(context)

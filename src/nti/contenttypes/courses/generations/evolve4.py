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

import zope.intid

from zope import component
from zope.component.hooks import site as current_site

from zope.security.interfaces import IPrincipal

from ZODB.POSException import POSError

from ..interfaces import INSTRUCTOR
from ..interfaces import ICourseCatalog
from ..interfaces import ICourseInstance
from ..interfaces import ICourseEnrollments

from ..index import IndexRecord
from ..index import install_enrollment_catalog

def do_evolve(context, generation=generation):

	conn = context.connection
	dataserver_folder = conn.root()['nti.dataserver']

	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(zope.intid.IIntIds)
	catalog = install_enrollment_catalog(dataserver_folder)

	total = 0
	sites = dataserver_folder['++etc++hostsites']
	for site in sites.values():
		with current_site(site):
			course_catalog = component.getUtility(ICourseCatalog)
			for entry in course_catalog.iterCatalogEntries():
				course = ICourseInstance(entry, None)
				if not course:
					continue

				# index instructor roles
				doc_id = intids.queryId(course)
				if doc_id is not None:
					for instructor in course.instructors or ():
						pid = IPrincipal(instructor).id
						record = IndexRecord(pid, entry.ntiid, INSTRUCTOR)
						catalog.index_doc(doc_id, record)
						total += 1

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

	logger.info('contenttypes.courses evolution %s done; %s object(s) indexed',
				generation, total)


def evolve(context):
	"""
	Evolve to generation 4 by indexing all enrollment records
	"""
	do_evolve(context, generation)

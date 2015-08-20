#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.intid import IIntIds

from zope.security.interfaces import IPrincipal

from .index import IndexRecord

from .interfaces import INSTRUCTOR
from .interfaces import ICourseInstance
from .interfaces import ICourseCatalogEntry

from . import get_enrollment_catalog

def index_course_instructors(context, catalog=None, intids=None):
	course = ICourseInstance(context, None)
	entry = ICourseCatalogEntry(context, None)
	if course is None or entry is None:
		return 0

	catalog = get_enrollment_catalog() if catalog is None else catalog
	intids = component.getUtility(IIntIds) if intids is None else intids
	doc_id = intids.queryId(course)
	if doc_id is None:
		return 0

	result = 0
	for instructor in course.instructors or ():
		principal = IPrincipal(instructor, None)
		if principal is None:
			continue
		pid = principal.id
		record = IndexRecord(pid, entry.ntiid, INSTRUCTOR)
		catalog.index_doc(doc_id, record)
		result += 1
	return result

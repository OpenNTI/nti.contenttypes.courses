#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.intid

from zope import component
from zope import interface

from ZODB.interfaces import IBroken
from ZODB.POSException import POSError

from nti.dataserver.interfaces import ISystemUserPrincipal
from nti.dataserver.interfaces import IPrincipalMetadataObjectsIntIds

from nti.site.hostpolicy import run_job_in_all_host_sites

from .interfaces import ICourseCatalog
from .interfaces import ICourseInstance

def get_uid(obj, intids=None):
	intids = component.getUtility(zope.intid.IIntIds) if intids is None else intids
	try:
		if IBroken.providedBy(obj):
			logger.warn("ignoring broken object %s", type(obj))
		elif obj is not None:
			uid = intids.queryId(obj)
			if uid is None:
				logger.warn("ignoring unregistered object %s", obj)
			else:
				return uid
	except (POSError):
		logger.error("ignoring broken object %s", type(obj))
	return None

def course_collector(catalog=None):
	catalog = component.getUtility(ICourseCatalog) if catalog is None else catalog
	for entry in catalog.iterCatalogEntries():
		course = ICourseInstance(entry, None)
		if course is not None:
			yield course

def outline_nodes_collector(course):
	result = []
	try:
		def _recurse(node):
			result.append(node)
			for child in node.values():
				_recurse(child)
		_recurse(course.Outline)
	except AttributeError:
		pass
	return result
			
@component.adapter(ISystemUserPrincipal)
@interface.implementer(IPrincipalMetadataObjectsIntIds)
class _CoursePrincipalObjectsIntIds(object):

	__slots__ = ()
	
	def __init__(self, *args, **kwargs):
		pass

	def iter_intids(self, intids=None):
		result = set()
		intids = component.getUtility(zope.intid.IIntIds) if intids is None else intids
		def _collector():
			for course in course_collector():
				uid = get_uid(course, intids)
				if uid is not None:
					result.add(uid)
		run_job_in_all_host_sites(_collector)
		for uid in result:
			yield uid

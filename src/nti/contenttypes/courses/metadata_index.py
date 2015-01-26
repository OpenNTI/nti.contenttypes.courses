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

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal
from nti.dataserver.interfaces import IPrincipalMetadataObjectsIntIds

from nti.site.hostpolicy import run_job_in_all_host_sites

from nti.utils.property import Lazy

from .interfaces import ICourseCatalog
from .interfaces import ICourseInstance
from .interfaces import IPrincipalEnrollments

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
	except (TypeError, POSError):
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
			
@interface.implementer(IPrincipalMetadataObjectsIntIds)
class _BasePrincipalObjectsIntIds(object):
	
	def __init__(self, *args, **kwargs):
		pass

	@Lazy
	def _intids(self):
		return component.getUtility(zope.intid.IIntIds)
	
	def iter_intids(self, intids=None):
		raise NotImplementedError()

@component.adapter(ISystemUserPrincipal)
class _CoursePrincipalObjectsIntIds(_BasePrincipalObjectsIntIds):

	def iter_intids(self, intids=None):
		result = set()
		intids = self._intids if intids is None else intids
		def _collector():
			for course in course_collector():
				uid = get_uid(course, intids)
				if uid is not None:
					result.add(uid)
		run_job_in_all_host_sites(_collector)
		for uid in result:
			yield uid

@component.adapter(ISystemUserPrincipal)
class _OutlinePrincipalObjectsIntIds(_BasePrincipalObjectsIntIds):

	def iter_intids(self, intids=None):
		result = set()
		intids = self._intids if intids is None else intids
		def _collector():
			for course in course_collector():
				for node in outline_nodes_collector(course):
					uid = get_uid(node, intids)
					if uid is not None:
						result.add(uid)
		run_job_in_all_host_sites(_collector)
		for uid in result:
			yield uid

@component.adapter(IUser)
class _EnrollmentPrincipalObjectsIntIds(_BasePrincipalObjectsIntIds):

	def __init__(self, user):
		self.user = user
	
	def iter_intids(self, intids=None):
		result = set()
		user = self.user
		intids = self._intids if intids is None else intids
		def _collector():
			for enrollments in component.subscribers( (user,), IPrincipalEnrollments):
				for enrollment in enrollments.iter_enrollments():
					uid = get_uid(enrollment, intids)
					if uid is not None:
						result.add(uid)
		run_job_in_all_host_sites(_collector)
		for uid in result:
			yield uid

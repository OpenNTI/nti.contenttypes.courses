#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

from nti.metadata.predicates import BasePrincipalObjects

from nti.site.hostpolicy import run_job_in_all_host_sites

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
class _CoursePrincipalObjects(BasePrincipalObjects):

	def iter_objects(self, intids=None):
		result = []
		def _collector():
			for course in course_collector():
				result.append(course)
				for node in outline_nodes_collector(course):
					result.append(node)
		run_job_in_all_host_sites(_collector)
		for obj in result:
			yield obj

@component.adapter(IUser)
class _EnrollmentPrincipalObjects(BasePrincipalObjects):

	def iter_objects(self):
		result = []
		user = self.user
		def _collector():
			for enrollments in component.subscribers((user,), IPrincipalEnrollments):
				for enrollment in enrollments.iter_enrollments():
					result.append(enrollment)
		run_job_in_all_host_sites(_collector)
		for obj in result:
			yield obj

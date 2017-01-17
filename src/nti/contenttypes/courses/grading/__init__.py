#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.contenttypes.courses.grading.parser import GRADING_POLICY_KEY

from nti.contenttypes.courses.grading.parser import parse_grading_policy
from nti.contenttypes.courses.grading.parser import reset_grading_policy
from nti.contenttypes.courses.grading.parser import fill_grading_policy_from_key
from nti.contenttypes.courses.grading.parser import set_grading_policy_for_course

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

@component.adapter(ICourseInstance)
@interface.implementer(ICourseGradingPolicy)
def grading_policy_for_course(course):
	annotations = IAnnotations(course)
	try:
		result = annotations[GRADING_POLICY_KEY]
	except KeyError:
		result = None
	return result
_grading_policy_for_course = grading_policy_for_course


def find_grading_policy_for_course(context):
	course = ICourseInstance(context, None)
	if course is None:
		return None
	registry = component
	try:
		# Courses may be ISites
		registry = course.getSiteManager()
		names = ('',)
	except LookupError:
		# try content pacakges
		names = [x.ntiid for x in get_course_packages(course)]
		# try catalog entry
		entry = ICourseCatalogEntry(course, None)
		if entry:
			names.append(entry.ntiid)
			names.append(entry.ProviderUniqueID)

	for name in names or ():
		try:
			return registry.getUtility(ICourseGradingPolicy, name=name)
		except LookupError:
			pass

	# We need to actually be registering these as annotations
	return ICourseGradingPolicy(course, None)

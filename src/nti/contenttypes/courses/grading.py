#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component
from zope.annotation.interfaces import IAnnotations

from .interfaces import ICourseInstance
from .interfaces import ICourseSubInstance
from .interfaces import ICourseGradingPolicy

GRADING_POLICY_KEY = 'CourseGradingPolicy'

@component.adapter(ICourseInstance)
@interface.implementer(ICourseGradingPolicy)
def _grading_policy_for_course(course):
	annotations = IAnnotations(course)
	try:
		result = annotations[GRADING_POLICY_KEY]
	except KeyError:
		result = None
	return result

@component.adapter(ICourseSubInstance)
@interface.implementer(ICourseGradingPolicy)
def _grading_policy_for_course_subinstance(course):
	result = _grading_policy_for_course(course)
	if result is None:
		result = _grading_policy_for_course(course.__parent__.__parent__)
	return result

@component.adapter(ICourseInstance)
@interface.implementer(ICourseGradingPolicy)
def set_grading_policy_for_course(course, policy=None):
	annotations = IAnnotations(course)
	if policy is None and GRADING_POLICY_KEY in annotations:
		del annotations[GRADING_POLICY_KEY]
	else:
		assert ICourseGradingPolicy.providedBy(policy)
		annotations[GRADING_POLICY_KEY] = policy
		policy.__parent__ = course # take ownership
		policy.__name__ = policy.__name__ or GRADING_POLICY_KEY

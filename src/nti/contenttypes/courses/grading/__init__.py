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

from ..interfaces import ICourseInstance

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

def set_grading_policy_for_course(course, policy=None):
	annotations = IAnnotations(course)
	if policy is None:
		if GRADING_POLICY_KEY in annotations:
			del annotations[GRADING_POLICY_KEY]
		else:
			return False
	else:
		assert ICourseGradingPolicy.providedBy(policy)
		annotations[GRADING_POLICY_KEY] = policy
		policy.__parent__ = course  # take ownership
		policy.__name__ = policy.__name__ or GRADING_POLICY_KEY
	return True

# re-export
from .parser import parse_grading_policy
from .parser import reset_grading_policy
from .parser import fill_grading_policy_from_key

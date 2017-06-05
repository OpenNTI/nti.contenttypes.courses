#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.contenttypes.courses.grading.parser import GRADING_POLICY_KEY

from nti.contenttypes.courses.grading.parser import parse_grading_policy
from nti.contenttypes.courses.grading.parser import reset_grading_policy
from nti.contenttypes.courses.grading.parser import fill_grading_policy_from_key
from nti.contenttypes.courses.grading.parser import set_grading_policy_for_course

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import find_interface


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


@component.adapter(ICourseGradingPolicy)
@interface.implementer(ICourseInstance)
def grading_policy_to_course(policy):
    return find_interface(policy, ICourseInstance, strict=False)


def find_grading_policy_for_course(context):
    course = ICourseInstance(context, None)
    return ICourseGradingPolicy(course, None)

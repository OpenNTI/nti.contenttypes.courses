#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope.annotation.interfaces import IAnnotations

from nti.assessment.interfaces import IQAssignmentPolicies

from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

#: Grading policy course annotation key
GRADING_POLICY_KEY = u'CourseGradingPolicy'

logger = __import__('logging').getLogger(__name__)


def reset_grading_policy(course):
    return set_grading_policy_for_course(course, None)


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


def parse_grading_policy(course, key):
    __traceback_info__ = key, course
    policy = ICourseGradingPolicy(course, None)
    if policy is not None and key.lastModified <= policy.lastModified:
        return False

    json = key.readContentsAsYaml()
    factory = find_factory_for(json)
    policy = factory()
    update_from_external_object(policy, json)

    set_grading_policy_for_course(course, policy)
    policy.synchronize()
    policy.lastModified = key.lastModified
    return True


def fill_grading_policy_from_key(course, key):
    result = parse_grading_policy(course, key)
    if not result:
        policy = ICourseGradingPolicy(course, None)
        assignment_policies = IQAssignmentPolicies(course, None)
        if policy is not None and assignment_policies is not None:
            policy.updateLastModIfGreater(assignment_policies.lastModified)
    return result

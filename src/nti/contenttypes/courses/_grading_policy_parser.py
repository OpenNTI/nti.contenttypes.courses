#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from .interfaces import ICourseGradingPolicy

from .grading import set_grading_policy_for_course

def reset_grading_policy(course):
	set_grading_policy_for_course(course, None)

def parse_grading_policy(course, key):
	
	__traceback_info__ = key, course

	policy = ICourseGradingPolicy(course, None)
	if policy is not None and key.lastModified <= policy.lastModified:
		return policy

	json = key.readContentsAsYaml()
	factory = find_factory_for(json)
	policy = factory()
	update_from_external_object(policy, json)
	
	set_grading_policy_for_course(course, policy)
	policy.synchronize()

	return policy

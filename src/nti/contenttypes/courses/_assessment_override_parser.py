#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reads the assignment overrides and policies and synchronizes them.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IQAssessmentDateContext

from nti.externalization.datetime import datetime_from_string

from nti.ntiids.ntiids import validate_ntiid_string

from .interfaces import SUPPORTED_DATE_KEYS
from .interfaces import SUPPORTED_PVE_INT_KEYS

def reset_asg_missing_key(course):
	IQAssessmentDateContext(course).clear()
	result = IQAssessmentPolicies(course).clear()
	return result

def fill_asg_from_key(course, key):
	"""
	XXX Fill in description

	Unlike that function, this function does set the last modified
	time to the time of that key (and sets the root of the catalog entry to
	the key). It also only does anything if the modified time has
	changed.

	:return: The entry
	"""

	# Note that regular courses do not track date contexts, so
	# we do the comparison of dates based on the policies

	__traceback_info__ = key, course

	dates = IQAssessmentDateContext(course)
	policies = IQAssessmentPolicies(course)
	if key.lastModified <= policies.lastModified:
		return False

	reset_asg_missing_key(course)
	json = key.readContentsAsYaml()
	dates.lastModified = key.lastModified
	policies.lastModified = key.lastModified

	dropped_policies_keys = SUPPORTED_DATE_KEYS + ('Title',)
	for key, val in json.items():
		policy = policies.getPolicyForAssessment(key)
		if policy and policy.get('locked', False):
			continue

		validate_ntiid_string(key)
		if not isinstance(val, dict):
			raise ValueError("Expected a dictionary")

		stored_dates = dict()
		for k in SUPPORTED_DATE_KEYS:
			if k in val:
				date_str = val[k]
				__traceback_info__ = key, k, date_str
				stored_dates[k] = datetime_from_string(date_str) if date_str else None

		# Date policy is stored in its own map
		dates[key] = stored_dates

		for k in SUPPORTED_PVE_INT_KEYS:
			if k not in val:
				continue
			int_val = val.get(k)
			try:
				int_val = int(int_val)
				assert int_val > 0
			except (AssertionError, TypeError, ValueError):
				raise ValueError("Bad postive integer value: %r" % int_val)
			val[k] = int_val

		# Policies stores it directly, with the exception
		# of things we know we don't want/need
		policies[key] = {k: v for k, v in val.items()
						 if k not in dropped_policies_keys}

	return True

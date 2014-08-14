#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reads the assignment overrides and policies and synchronizes them.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.assessment.interfaces import IQAssignmentDateContext
from nti.assessment.interfaces import IQAssignmentPolicies

from nti.ntiids.ntiids import validate_ntiid_string
from nti.externalization.datetime import datetime_from_string

def reset_asg_missing_key(course):
	IQAssignmentDateContext(course).clear()
	IQAssignmentPolicies(course).clear()

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

	policies = IQAssignmentPolicies(course)
	dates = IQAssignmentDateContext(course)
	if key.lastModified <= policies.lastModified:
		return dates

	reset_asg_missing_key(course)

	json = key.readContentsAsJson()
	dates.lastModified = key.lastModified

	supported_date_keys = ('available_for_submission_beginning',
						   'available_for_submission_ending')
	dropped_policies_keys = supported_date_keys + ('Title',)
	for key, val in json.items():
		validate_ntiid_string(key)
		if not isinstance(val, dict):
			raise ValueError("Expected a dictionary")

		stored_dates = dict()
		for k in supported_date_keys:
			if k in val:
				date_string = val[k]
				__traceback_info__ = key, k, date_string
				stored_dates[k] = datetime_from_string(date_string) if date_string else None

		dates[key] = stored_dates
		# Policies stores it directly, with the exception
		# of things we know we don't want/need

		policies[key] = {k: v for k,v in val.items()
						 if k not in dropped_policies_keys}

	return dates

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reads the assignment overrides and synchronizes them.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.assessment.interfaces import IQAssignmentDateContext
from nti.ntiids.ntiids import validate_ntiid_string
from nti.externalization.datetime import datetime_from_string

def reset_asg_missing_key(course):
	IQAssignmentDateContext(course).clear()

def fill_asg_from_key(course, key):
	"""
	XXX Fill in description

	Unlike that function, this function does set the last modified
	time to the time of that key (and sets the root of the catalog entry to
	the key). It also only does anything if the modified time has
	changed.

	:return: The entry
	"""

	dates = IQAssignmentDateContext(course)
	if key.lastModified <= dates.lastModified:
		return dates

	reset_asg_missing_key(course)

	json = key.readContentsAsJson()
	dates.lastModified = key.lastModified

	supported_keys = ('available_for_submission_beginning',
					  'available_for_submission_ending')
	for key, val in json.items():
		validate_ntiid_string(key)

		stored_val = dict()
		for k in supported_keys:
			if k in val:
				__traceback_info__ = key, k, val[k]
				stored_val[k] = datetime_from_string(val[k])

		dates[key] = stored_val



	return dates

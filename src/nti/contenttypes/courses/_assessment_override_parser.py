#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reads the assignment overrides and policies and synchronizes them.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from persistent.mapping import PersistentMapping

from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IQAssessmentDateContext

from nti.contenttypes.courses.interfaces import SUPPORTED_DATE_KEYS
from nti.contenttypes.courses.interfaces import SUPPORTED_PVE_INT_KEYS

from nti.externalization.datetime import datetime_from_string

from nti.ntiids.ntiids import validate_ntiid_string


def reset_asg_missing_key(course):
    dates = IQAssessmentDateContext(course)
    policies = IQAssessmentPolicies(course)
    # Always test locked status before clearing state in dates and policies.
    for key in policies.assessments():
        if not policies.get(key, 'locked', False):
            del policies[key]
            try:
                del dates[key]
            except KeyError:
                pass
    return policies


def fill_asg_from_json(course, index, lastModified=0):

    logger.info('Reading in assignment policies for %s', course)

    # remove previous data
    reset_asg_missing_key(course)

    dates = IQAssessmentDateContext(course)
    policies = IQAssessmentPolicies(course)

    dates.lastModified = lastModified
    policies.lastModified = lastModified

    dropped_policies_keys = SUPPORTED_DATE_KEYS + ('Title', 'locked')
    for key, val in index.items():
        if policies.get(key, 'locked', False):
            logger.warn("Policy for %s is locked", key)
            continue
        if val is None:
            continue
        validate_ntiid_string(key)
        if not isinstance(val, dict):
            raise ValueError("Expected a dictionary")
        elif not val:
            continue
        stored_dates = PersistentMapping()
        for k in SUPPORTED_DATE_KEYS:
            if k in val:
                date_str = val[k]
                __traceback_info__ = key, k, date_str
                if date_str:
                    stored_dates[k] = datetime_from_string(date_str)
                else:
                    stored_dates[k] = None

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
                raise ValueError("Bad positive integer value: %r" % int_val)
            val[k] = int_val

        # Policies stores it directly, with the exception
        # of things we know we don't want/need
        policies[key] = PersistentMapping({k: v for k, v in val.items()
                                           if k not in dropped_policies_keys})

    return policies


def fill_asg_from_key(course, key):
    # Note that regular courses do not track date contexts, so
    # we do the comparison of dates based on the policies
    __traceback_info__ = key, course
    policies = IQAssessmentPolicies(course)
    if key.lastModified <= policies.lastModified:
        return False
    index = key.readContentsAsYaml()
    fill_asg_from_json(course, index, key.lastModified)
    return True

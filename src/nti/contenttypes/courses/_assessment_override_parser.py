#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reads the assignment overrides and policies and synchronizes them.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from collections import Mapping

from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IQAssessmentDateContext

from nti.contenttypes.courses.interfaces import SUPPORTED_DATE_KEYS
from nti.contenttypes.courses.interfaces import SUPPORTED_PVE_INT_KEYS

from nti.externalization.datetime import datetime_from_string

from nti.ntiids.ntiids import validate_ntiid_string

logger = __import__('logging').getLogger(__name__)


def reset_asg_missing_key(course, force=False):
    dates = IQAssessmentDateContext(course)
    policies = IQAssessmentPolicies(course)
    # Always test locked status before clearing state in dates and policies.
    for key in policies.assessments():
        if force or not policies.get(key, 'locked', False):
            del policies[key]
            try:
                del dates[key]
            except KeyError:
                pass
    return policies


def fill_asg_from_json(course, index, lastModified=0, force=False):
    logger.info('Reading in assignment policies for %s', course)
    # remove previous data
    reset_asg_missing_key(course, force)
    # set last mod dates
    dates = IQAssessmentDateContext(course)
    policies = IQAssessmentPolicies(course)
    dates.lastModified = lastModified
    policies.lastModified = lastModified
    # loop through values
    dropped_policies_keys = SUPPORTED_DATE_KEYS + ('Title', 'locked')
    for ntiid, values in index.items():
        # check for locked status
        locked = policies.get(ntiid, 'locked', False)
        if not force and locked:
            logger.warn("Policy for %s is locked", ntiid)
            continue
        # validate input values
        if values is None:
            continue
        validate_ntiid_string(ntiid)
        if not isinstance(values, Mapping):
            raise ValueError("Expected a mapping object")
        elif not values:
            continue
        # save locked value
        locked = values.get('locked', False)
        if force and locked:
            policies.set(ntiid, 'locked', True)
        # validate date keys in policy
        for date_key in SUPPORTED_DATE_KEYS:
            if date_key in values:
                date_str = values[date_key]
                __traceback_info__ = ntiid, date_key, date_str
                if date_str:
                    value = datetime_from_string(date_str)
                else:
                    value = None
                dates.set(ntiid, date_key, value)
        # validate positive integer keys in policy
        for k in SUPPORTED_PVE_INT_KEYS:
            if k not in values:
                continue
            int_val = values.get(k)
            if int_val is None:
                continue
            try:
                int_val = int(int_val)
                assert int_val > 0
            except (AssertionError, TypeError, ValueError):
                raise ValueError("Bad positive integer value: %r" % int_val)
            values[k] = int_val
        # store values directly, with the exception
        # of things we know we don't want/need
        for k, v in values.items():
            if k not in dropped_policies_keys:
                policies.set(ntiid, k, v)
    # return
    return policies


def fill_asg_from_key(course, key, force=False):
    # Note that regular courses do not track date contexts, so
    # we do the comparison of dates based on the policies
    __traceback_info__ = key, course
    policies = IQAssessmentPolicies(course)
    if key.lastModified <= policies.lastModified:
        return False
    index = key.readContentsAsYaml()
    fill_asg_from_json(course, index, key.lastModified, force)
    return True

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.assessment.interfaces import IQAssignmentPolicies

def validate_assigment_policies(course):
	policies = IQAssignmentPolicies(course, None)
	if not policies:
		return


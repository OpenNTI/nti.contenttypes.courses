#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssignmentPolicies
from nti.assessment.interfaces import IQAssignmentPolicyValidator

from .interfaces import ICourseCatalogEntry

@interface.implementer(IQAssignmentPolicyValidator)
class DefaultAssignmentPolicyValidator(object):
	
	def validate(self, ntiid, policy):
		assignment = component.queryUtility(IQAssignment, name=ntiid)
		if assignment is None:
			logger.warn("Could not find assignment with ntiid %s", ntiid)
			
		auto_grade = policy.get('auto_grade')
		if not auto_grade:
			return
		total_points = auto_grade.get('total_points')
		try:
			assert total_points is None or int(total_points) >= 0
		except (AssertionError, TypeError, ValueError):
			msg = "Invalid total points in policy for %s" % ntiid
			raise ValueError(msg)
		
		name = auto_grade.get('name')
		if not name:
			return
		
		if name.lower() in ('pointbased'):
			assert assignment, 'Could not find assignment %s' % ntiid
			assert total_points, "Invalid total points in policy for %s" % ntiid
		else:
			logger.warn("Don't know how to validate policy %s in assignment", 
						name, ntiid)

def validate_assigment_policies(course): 
	course_policies = IQAssignmentPolicies(course, None)
	if not course_policies:
		return

	assignments = course_policies.assignments()
	policies = {a:course_policies.getPolicyForAssignment(a) for a in assignments}
	
	# let's try the course
	registry = component
	validator = IQAssignmentPolicyValidator(course, None)
	if validator is None:
		# Courses may be ISites
		try:
			names = ('',)
			registry = course.getSiteManager()
		except LookupError:
			entry = ICourseCatalogEntry(course, None)
			if entry:
				names = (entry.ntiid,)
		
		for name in names:
			try:
				validator = registry.getUtility(IQAssignmentPolicyValidator, name=name)
				break
			except LookupError:
				validator = None
	
	if validator is None:
		## let's try default validator
		validator = DefaultAssignmentPolicyValidator()
	
	# go through policies
	for k,v in policies.items():
		validator.validate(k, v)

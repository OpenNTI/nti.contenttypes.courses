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

from nti.ntiids.ntiids import is_valid_ntiid_string

from .interfaces import ICourseCatalogEntry

@interface.implementer(IQAssignmentPolicyValidator)
class DefaultAssignmentPolicyValidator(object):
	
	def question_points(self, auto_grade, ntiid):
		question_map = auto_grade.get('questions') or auto_grade
		points = question_map.get(ntiid) or question_map.get('default')
		return points
	
	def validate(self, ntiid, policy):
		assignment = None
		
		if is_valid_ntiid_string(ntiid):
			assignment = component.queryUtility(IQAssignment, name=ntiid)
			if assignment is None:
				logger.debug("Could not find assignment with ntiid %s", ntiid)
		else:
			return
			
		auto_grade = policy.get('auto_grade')
		if not auto_grade:
			return
		total_points = auto_grade.get('total_points')
		try:
			assert int(total_points) >= 0
		except (AssertionError, TypeError, ValueError):
			msg = "Invalid total points in policy for %s" % ntiid
			raise ValueError(msg)
		
		name = auto_grade.get('name')
		if not name:
			return
		
		if name.lower() in ('pointbased'):
			if assignment is None:
				raise AssertionError('Could not find assignment %s' % ntiid)

			for part in assignment.parts:
				for question in part.question_set.questions:
					q_ntiid = question.ntiid
					points = self.question_points(auto_grade, ntiid)
					if not points or int(points) <= 0:
						msg = "Invalid points in policy for question %s" % q_ntiid
						raise ValueError(msg)
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

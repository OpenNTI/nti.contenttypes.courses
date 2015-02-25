#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import Mapping

from zope import component
from zope import interface

from zope.mimetype.interfaces import IContentTypeAware

from zope.container.contained import Contained

from persistent import Persistent

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssignmentPolicies

from nti.common.property import Lazy
from nti.common.property import alias
from nti.common.maps import CaseInsensitiveDict

from nti.externalization.representation import WithRepr

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from ..interfaces import ICourseInstance

from .interfaces import IEqualGroupGrader
from .interfaces import ICourseGradingPolicy

def get_assignment_policies(course):
	result = IQAssignmentPolicies(course, None)
	return result

def get_assignment(ntiid):
	assignment = component.queryUtility(IQAssignment, name=ntiid)
	return assignment

@interface.implementer(IEqualGroupGrader, IContentTypeAware)
class BaseMixin(Persistent, SchemaConfigured, Contained):
	
	parameters = {}

	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		Persistent.__init__(self)
		SchemaConfigured.__init__(self, *args, **kwargs)

@WithRepr
@interface.implementer(IEqualGroupGrader)
class EqualGroupGrader(BaseMixin):
	createDirectFieldProperties(IEqualGroupGrader)
	
	mime_type = mimeType = 'application/vnd.nextthought.courses.grading.equalgroupgrader'
	
	groups = alias('Groups')
		
	def validate(self):
		assert self.groups, "must specify at least a group"
		
		count = 0
		for name, weight in self.groups.items():
			assert weight > 0 and weight <=1, "invalid weight for category %s" % name
			count += weight
			
		assert  round(count, 2) <= 1.0, \
				"total category weight must be less than or equal to one"

		categories = self.categories
		for name in categories.keys():
			assert name in self.groups, \
				   "%s is an invalid group name" % name
		
		seen = set()
		for name in self.groups.keys():
			ids = categories.get(name)
			assert ids, \
				   "No assignment are defined for category %s" % name
			for ntiid in ids:
				assert ntiid not in seen, \
					   "Assignment %s is in multiple groups" % ntiid
				seen.add(ntiid)
				
				assignment = get_assignment(ntiid)
				if assignment is None:
					raise AssertionError("assignment does not exists", ntiid)
	@Lazy
	def categories(self):
		result = CaseInsensitiveDict(set)
		policies = get_assignment_policies(self.course)
		if not policies: 
			for assignment in policies.assignments():
				policy = policies.getPolicyForAssignment(assignment)
				if not policy or not isinstance(policy, Mapping):
					continue		  
				if policy.get('excluded', False) or 'grader' not in policy:
					continue
				group = policy['grader'].get('group')
				if group:
					result.setdefault(group, set())
					result[group].add(assignment)
		return result

	@Lazy
	def rev_categories(self):
		result = CaseInsensitiveDict()
		for name, assignments in self.categories.items():
			for assignment in assignments:
				result[assignment] = name
		return result
	
	@property
	def course(self):
		return getattr(self.__parent__, 'course', None)

	def __len__(self):
		return len(self.groups)
	
	def __getitem__(self, key):
		return self.groups[key]
	
	def __iter__(self):
		return iter(self.groups)

@WithRepr
@interface.implementer(ICourseGradingPolicy)
class DefaultCourseGradingPolicy(BaseMixin):
	createDirectFieldProperties(ICourseGradingPolicy)

	mime_type = mimeType = 'application/vnd.nextthought.courses.grading.defaultpolicy'
	
	grader = alias('Grader')
	
	def __setattr__(self, name, value):
		if name in ("Grader", "grader") and value is not None:
			value.__parent__ = self
		return SchemaConfigured.__setattr__(self, name, value)

	def validate(self):
		assert self.grader, "must specify a grader"
		self.grader.validate()
	
	def synchronize(self):
		course = self.course
		assert course, "must policy must be attached to a course"
		self.validate()
		
	@property
	def course(self):
		return ICourseInstance(self.__parent__, None)

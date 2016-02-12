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

from zope.container.contained import Contained

from zope.mimetype.interfaces import IContentTypeAware

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssignmentPolicies

from nti.common.property import alias
from nti.common.property import CachedProperty

from nti.contenttypes.courses.grading.interfaces import IEqualGroupGrader
from nti.contenttypes.courses.grading.interfaces import ICategoryGradeScheme
from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dublincore.time_mixins import CreatedAndModifiedTimeMixin

from nti.externalization.representation import WithRepr

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.zodb.persistentproperty import PersistentPropertyHolder

def get_assignment_policies(course):
	result = IQAssignmentPolicies(course, None)
	return result

def get_assignment(ntiid):
	assignment = component.queryUtility(IQAssignment, name=ntiid)
	return assignment

@interface.implementer(IContentTypeAware)
class BaseMixin(PersistentPropertyHolder, SchemaConfigured, Contained):

	parameters = {} # IContentTypeAware

	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		PersistentPropertyHolder.__init__(self)
		SchemaConfigured.__init__(self, *args, **kwargs)

@WithRepr
@interface.implementer(ICategoryGradeScheme)
class CategoryGradeScheme(BaseMixin):

	mime_type = mimeType = 'application/vnd.nextthought.courses.grading.categorygradescheme'

	createDirectFieldProperties(ICategoryGradeScheme)

	LatePenalty = 1

	weight = alias('Weight')
	penalty = alias('LatePenalty')
	dropLowest = alias('DropLowest')

@WithRepr
@interface.implementer(IEqualGroupGrader)
class EqualGroupGrader(CreatedAndModifiedTimeMixin, BaseMixin):
	createDirectFieldProperties(IEqualGroupGrader)

	mime_type = mimeType = 'application/vnd.nextthought.courses.grading.equalgroupgrader'

	groups = alias('Groups')

	def validate(self):
		assert self.groups, "must specify at least a group"

		count = 0
		for name, category in self.groups.items():
			weight = category.Weight
			assert weight > 0 and weight <= 1, "invalid weight for category %s" % name
			count += weight

		assert  round(count, 2) <= 1.0, \
				"total category weight must be less than or equal to one"

		categories = self._raw_categories()
		for name in categories.keys():
			assert name in self.groups, \
				   "%s is an invalid group name" % name

		seen = set()
		for name in self.groups.keys():
			data = categories.get(name)
			assert data, \
				   "No assignment are defined for category %s" % name
			for ntiid in [x['assignment'] for x in data]:
				assert ntiid not in seen, \
					   "Assignment %s is in multiple groups" % ntiid
				seen.add(ntiid)

				assignment = get_assignment(ntiid)
				if assignment is None:
					raise AssertionError("assignment does not exists", ntiid)

	@property
	def lastSynchronized(self):
		self_lastModified = self.lastModified or 0
		parent_lastSynchronized = getattr(self.course, 'lastSynchronized', None) or 0
		return max(self_lastModified, parent_lastSynchronized)

	def _raw_categories(self):
		result = {}
		policies = get_assignment_policies(self.course)
		if policies is not None:
			for assignment in policies.assignments():
				policy = policies.getPolicyForAssignment(assignment)
				if not policy or policy.get('excluded', False):
					continue

				auto_grade = policy.get('auto_grade') or {}
				grader = policy.get('grader') or auto_grade.get('grader')
				if not grader:
					continue

				group = grader.get('group')
				if group:
					data = dict()
					total_points = auto_grade.get('total_points')
					if total_points:
						data['total_points'] = data['points'] = total_points
					data.update(grader)  # override
					data['assignment'] = assignment  # save

					result.setdefault(group, [])
					result[group].append(data)
		return result

	@CachedProperty('lastSynchronized')
	def _categories(self):
		result = self._raw_categories()
		return result

	def _raw_rev_categories(self):
		result = {}
		for name, data in self._categories.items():
			for assignment in [x['assignment'] for x in data]:
				result[assignment] = name
		return result

	@CachedProperty('lastSynchronized')
	def _rev_categories(self):
		result = self._raw_rev_categories()
		return result

	def _raw_assignments(self):
		return tuple(self._raw_rev_categories().keys())

	@CachedProperty('lastSynchronized')
	def _assignments(self):
		result = self._raw_assignments()
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
class DefaultCourseGradingPolicy(CreatedAndModifiedTimeMixin, BaseMixin):
	createDirectFieldProperties(ICourseGradingPolicy)

	mime_type = mimeType = 'application/vnd.nextthought.courses.grading.defaultpolicy'

	grader = alias('Grader')

	def __setattr__(self, name, value):
		if name in ("Grader", "grader") and value is not None:
			value.__parent__ = self
		return BaseMixin.__setattr__(self, name, value)

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

	def grade(self, *args, **kwargs):
		raise NotImplementedError()

	def updateLastMod(self, t=None):
		result = super(DefaultCourseGradingPolicy, self).updateLastMod(t)
		if self.grader is not None:
			self.grader.updateLastMod(t)
		return result

	def updateLastModIfGreater(self, t):
		result = super(DefaultCourseGradingPolicy, self).updateLastModIfGreater(t)
		if self.grader is not None:
			self.grader.updateLastModIfGreater(t)
		return result

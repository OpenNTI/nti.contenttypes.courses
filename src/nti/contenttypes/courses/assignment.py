#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for assessments/assignment.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.annotation.factory import factory as an_factory

from zope.container.contained import Contained

from persistent.mapping import PersistentMapping

from nti.assessment.interfaces import IQAssignmentPolicies
from nti.assessment.interfaces import IQAssignmentDateContext

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.externalization.persistence import NoPickle

from .interfaces import ICourseInstance

@interface.implementer(IQAssignmentDateContext)
class EmptyAssignmentDateContext(object):
	"""
	Used when there is no context to adjust the dates.

	Not registered, but useful for testing.
	"""

	def __init__(self, context):
		pass

	def assessments(self):
		return ()
	assignments = assessments

	def of(self, asg):
		return asg

	def clear(self):
		pass

	def __setitem__(self, key, valu):
		pass

@NoPickle
class _Dates(object):

	def __init__(self, mapping, asg):
		self._asg = asg
		self._mapping = mapping

	def __getattr__(self, name):
		try:
			return self._mapping[self._asg.ntiid][name]
		except KeyError:
			return getattr(self._asg, name)

@interface.implementer(IQAssignmentDateContext)
@component.adapter(ICourseInstance)
class MappingAssignmentDateContext(Contained,
								   PersistentCreatedAndModifiedTimeObject):
	"""
	A persistent mapping of assessment_ntiid -> {'available_for_submission_beginning': datetime}
	"""

	_SET_CREATED_MODTIME_ON_INIT = False

	def __init__(self):
		PersistentCreatedAndModifiedTimeObject.__init__(self)
		self._mapping = PersistentMapping()

	def assessments(self):
		return list(self._mapping.keys())
	assignments = assessments  # BWC

	def of(self, asg):
		if asg.ntiid in self._mapping:
			return _Dates(self._mapping, asg)
		return asg

	def clear(self):
		self._mapping.clear()

	def __setitem__(self, key, value):
		self._mapping[key] = value

CourseSubInstanceAssignmentDateContextFactory = an_factory(MappingAssignmentDateContext)

@component.adapter(ICourseInstance)
@interface.implementer(IQAssignmentPolicies)
class MappingAssignmentPolicies(Contained, PersistentCreatedAndModifiedTimeObject):
	"""
	A persistent mapping of assessment ids to policy information,
	that is uninterpreted by this module.
	"""

	_SET_CREATED_MODTIME_ON_INIT = False

	def __init__(self):
		PersistentCreatedAndModifiedTimeObject.__init__(self)
		self._mapping = PersistentMapping()

	def assessments(self):
		return list(self._mapping.keys())
	assignments = assessments  # BWC

	def size(self):
		return len(self._mapping)

	def clear(self):
		size = self.size()
		self._mapping.clear()
		return size > 0

	def __setitem__(self, key, value):
		self._mapping[key] = value

	def getPolicyForAssessment(self, key):
		return self._mapping.get(key, {})
	getPolicyForAssignment = getPolicyForAssessment  # BWC

	def __len__(self):
		return self.size()

	def __bool__(self):
		return bool(self._mapping)
	__nonzero__ = __bool__

CourseInstanceAssignmentPoliciesFactory = an_factory(MappingAssignmentPolicies)

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

from .interfaces import ICourseInstance
from .interfaces import ICourseSubInstance
from nti.assessment.interfaces import IQAssignmentDateContext

from zope.container.contained import Contained
from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject
from persistent.mapping import PersistentMapping

from nti.externalization.persistence import NoPickle

from zope.annotation.factory import factory as an_factory

@interface.implementer(IQAssignmentDateContext)
@component.adapter(ICourseInstance)
class EmptyAssignmentDateContext(object):
	"""
	Used when there is no context to adjust the dates.

	Initially at least, plain course instances do not
	adjust dates, only subsections do.
	"""

	def __init__(self, context):
		pass

	def of(self, asg):
		return asg

@NoPickle
class _Dates(object):

	def __init__(self, mapping, asg):
		self._mapping = mapping
		self._asg = asg

	def __getattr__(self, name):
		try:
			return self._mapping[self._asg.ntiid][name]
		except KeyError:
			return getattr(self._asg, name)

@interface.implementer(IQAssignmentDateContext)
@component.adapter(ICourseSubInstance)
class MappingAssignmentDateContext(Contained,
								   PersistentCreatedAndModifiedTimeObject):
	"""
	A persistent mapping of assignment_ntiid -> {'available_for_submission_beginning': datetime}
	"""

	_SET_CREATED_MODTIME_ON_INIT = False

	def __init__(self):
		PersistentCreatedAndModifiedTimeObject.__init__(self)
		self._mapping = PersistentMapping()


	def of(self, asg):
		if asg.ntiid in self._mapping:
			return _Dates(self._mapping, asg)
		return asg

	def clear(self):
		self._mapping.clear()

	def __setitem__(self, key, value):
		self._mapping[key] = value


CourseSubInstanceAssignmentDateContextFactory = an_factory(MappingAssignmentDateContext)

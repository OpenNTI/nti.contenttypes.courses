#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementation of the course outline structure.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.annotation.interfaces import IAttributeAnnotatable

from zope.container.contained import Contained
from zope.container.contained import uncontained
from zope.container.constraints import checkObject
from zope.container.ordered import OrderedContainer  # this is persistent

from nti.coremetadata.mixins import RecordableMixin
from nti.coremetadata.mixins import CalendarPublishableMixin

from nti.dataserver.interfaces import SYSTEM_USER_ID
from nti.dataserver.interfaces import ITitledDescribedContent

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import AdaptingFieldProperty
from nti.schema.fieldproperty import createFieldProperties
from nti.schema.fieldproperty import createDirectFieldProperties

from .interfaces import ICourseOutline
from .interfaces import ICourseOutlineNode
from .interfaces import ICourseOutlineContentNode
from .interfaces import ICourseOutlineCalendarNode

@interface.implementer(IAttributeAnnotatable)
class _AbstractCourseOutlineNode(Contained, RecordableMixin, CalendarPublishableMixin):

	createFieldProperties(ITitledDescribedContent)
	createDirectFieldProperties(ICourseOutlineNode)
	__external_can_create__ = True

	creator = SYSTEM_USER_ID

	title = AdaptingFieldProperty(ITitledDescribedContent['title'])
	description = AdaptingFieldProperty(ITitledDescribedContent['description'])

	def append(self, node):
		try:
			name = node.ntiid
		except AttributeError:
			name = unicode(len(self))
		self[name] = node

	def __hash__(self):
		# We inherit an __eq__ from dict, but dict does not
		# like to be hashed (because mutable cache keys can be bad)
		# But we have an ACL and need to be hashable
		return hash(tuple(self.items()))

	def _delitemf(self, key):
		del self._data[key]
		self._order.remove(key)

	def reset(self, event=True):
		keys = list(self)
		for k in keys:
			if event:
				del self[k]
			else:
				self._delitemf(k)
	clear = reset

@interface.implementer(ICourseOutlineNode)
class CourseOutlineNode(_AbstractCourseOutlineNode,
						PersistentCreatedModDateTrackingObject,  # order mattters
						OrderedContainer):

	# XXX This class used to be persistent. Although there were
	# never any references explicitly stored to them, because it
	# was persistent and is a Container, the intid utility grabbed
	# the children when IObjectAdded fired. Now that we're not
	# persistent, those instances in the intid BTree cannot be
	# correctly read. So we define a broken object replacement
	# that our DB class factory will use instead.
	# JAM: 20140714: This is turned off because we now need to be
	# able to persist these items. Not sure what the implications are for
	# alpha, which was the only place that saw this error? I don't remember
	# the exact details...have to wait and see.
	# _v_nti_pseudo_broken_replacement_name = str('CourseOutlineNode_BROKEN')
	def __setitem__(self, key, value):
		checkObject(self, key, value)
		super(CourseOutlineNode, self).__setitem__(key, value)

	def __delitem__(self, key):
		uncontained(self[key], self, key)
		super(CourseOutlineNode, self).__delitem__(key)

@interface.implementer(ICourseOutlineCalendarNode)
class CourseOutlineCalendarNode(SchemaConfigured,
								CourseOutlineNode):
	createDirectFieldProperties(ICourseOutlineCalendarNode)

	AvailableEnding = AdaptingFieldProperty(ICourseOutlineCalendarNode['AvailableEnding'])
	AvailableBeginning = AdaptingFieldProperty(ICourseOutlineCalendarNode['AvailableBeginning'])

	def __init__(self, *args, **kwargs):
		SchemaConfigured.__init__(self, *args, **kwargs)
		CourseOutlineNode.__init__(self)

@interface.implementer(ICourseOutlineContentNode)
class CourseOutlineContentNode(CourseOutlineCalendarNode):
	createDirectFieldProperties(ICourseOutlineContentNode)

@interface.implementer(ICourseOutline)
class CourseOutline(CourseOutlineNode,
					PersistentCreatedModDateTrackingObject):
	createDirectFieldProperties(ICourseOutline)

	_SET_CREATED_MODTIME_ON_INIT = False
	__external_can_create__ = False

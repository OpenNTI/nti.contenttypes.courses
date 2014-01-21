#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementation of the course outline structure.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from .interfaces import ICourseOutline
from .interfaces import ICourseOutlineNode
from .interfaces import ICourseOutlineCalendarNode
from .interfaces import ICourseOutlineContentNode
from nti.dataserver.interfaces import ITitledDescribedContent

# We have no need or desire for these nodes to be Persistent (yet)
# so we cannot extend OrderedContainer:
# from zope.container.ordered import OrderedContainer
# Instead, we extend a regular OrderedDict and implement the container part ourself
from collections import OrderedDict
# Also note that the mixin:
# from nti.dataserver.containers import _CheckObjectOnSetMixin
# doesn't work with the OrderedContainer, so we have to do that ourself
from zope.container.constraints import checkObject
from zope.container.contained import Contained, setitem, uncontained

from nti.dataserver.datastructures import CreatedModDateTrackingObject

from nti.utils.schema import createDirectFieldProperties
from nti.utils.schema import createFieldProperties
from nti.utils.schema import SchemaConfigured
from nti.utils.schema import AdaptingFieldProperty

@interface.implementer(ICourseOutlineNode)
class CourseOutlineNode(Contained, OrderedDict):
	createFieldProperties(ITitledDescribedContent)
	createDirectFieldProperties(ICourseOutlineNode)
	__external_can_create__ = False

	title = AdaptingFieldProperty(ITitledDescribedContent['title'])
	description = AdaptingFieldProperty(ITitledDescribedContent['description'])

	def append(self, node):
		name = unicode(len(self))
		self[name] = node

	def __setitem__(self, key, value):
		checkObject(self, key, value)
		setitem(self, super(CourseOutlineNode,self).__setitem__, key, value)

	def __delitem__(self, key):
		uncontained(self[key], self, key)
		super(CourseOutlineNode,self).__delitem__(key)

	def updateOrder(self, order):
		raise TypeError("Ordering cannot be changed")

	def __reduce__(self):
		raise TypeError("Not meant to be persistent")

	def __hash__(self):
		# We inherit an __eq__ from dict, but dict does not
		# like to be hashed (because mutable cache keys can be bad)
		# But we have an ACL and need to be hashable
		return hash( tuple(self.items() ) )


@interface.implementer(ICourseOutlineCalendarNode)
class CourseOutlineCalendarNode(SchemaConfigured,
								CourseOutlineNode):
	createDirectFieldProperties(ICourseOutlineCalendarNode)

	def __init__(self,**kwargs):
		SchemaConfigured.__init__(self,**kwargs)
		CourseOutlineNode.__init__(self)

	AvailableBeginning = AdaptingFieldProperty(ICourseOutlineCalendarNode['AvailableBeginning'])
	AvailableEnding = AdaptingFieldProperty(ICourseOutlineCalendarNode['AvailableEnding'])


@interface.implementer(ICourseOutlineContentNode)
class CourseOutlineContentNode(CourseOutlineCalendarNode):
	createDirectFieldProperties(ICourseOutlineContentNode)

@interface.implementer(ICourseOutline)
class CourseOutline(CreatedModDateTrackingObject,
					CourseOutlineNode):
	createDirectFieldProperties(ICourseOutline)
	__external_can_create__ = False

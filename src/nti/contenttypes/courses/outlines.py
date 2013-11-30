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

from zope.container.ordered import OrderedContainer
from nti.dataserver.containers import _CheckObjectOnSetMixin
from nti.dataserver.datastructures import PersistentCreatedModDateTrackingObject

from nti.utils.schema import createDirectFieldProperties
from nti.utils.schema import createFieldProperties
from nti.utils.schema import SchemaConfigured

@interface.implementer(ICourseOutlineNode)
class CourseOutlineNode(_CheckObjectOnSetMixin,
						OrderedContainer):
	createFieldProperties(ITitledDescribedContent)
	createDirectFieldProperties(ICourseOutlineNode)
	__external_can_create__ = False
	def append(self, node):
		name = unicode(len(self))
		self[name] = node

@interface.implementer(ICourseOutlineCalendarNode)
class CourseOutlineCalendarNode(SchemaConfigured,
								CourseOutlineNode):
	createDirectFieldProperties(ICourseOutlineCalendarNode)

	def __init__(self,**kwargs):
		SchemaConfigured.__init__(self,**kwargs)
		CourseOutlineNode.__init__(self)

@interface.implementer(ICourseOutlineContentNode)
class CourseOutlineContentNode(CourseOutlineCalendarNode):
	createDirectFieldProperties(ICourseOutlineContentNode)

@interface.implementer(ICourseOutline)
class CourseOutline(PersistentCreatedModDateTrackingObject,
					CourseOutlineNode):
	createDirectFieldProperties(ICourseOutline)
	__external_can_create__ = False

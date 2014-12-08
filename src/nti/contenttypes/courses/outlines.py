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

# We have no need or desire for these nodes to be Persistent (yet)
# so we cannot extend OrderedContainer:
#from zope.container.ordered import OrderedContainer
# Instead, we extend a regular OrderedDict and implement the container part ourself
#from collections import OrderedDict
# Also note that the mixin:
# from nti.dataserver.containers import _CheckObjectOnSetMixin
# doesn't work with the OrderedContainer, so we have to do that ourself
from zope.container.constraints import checkObject
from zope.container.ordered import OrderedContainer
from zope.container.contained import Contained, uncontained

from nti.dataserver.interfaces import ITitledDescribedContent
from nti.dataserver.datastructures import PersistentCreatedModDateTrackingObject

# The exception to persistence is the top-level object, which
# we expect to modify in place, and possible store references to

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import AdaptingFieldProperty
from nti.schema.fieldproperty import createFieldProperties
from nti.schema.fieldproperty import createDirectFieldProperties

from .interfaces import ICourseOutline
from .interfaces import ICourseOutlineNode
from .interfaces import ICourseOutlineContentNode
from .interfaces import ICourseOutlineCalendarNode

class _AbstractCourseOutlineNode(Contained):

	createFieldProperties(ITitledDescribedContent)
	createDirectFieldProperties(ICourseOutlineNode)
	
	__external_can_create__ = False

	title = AdaptingFieldProperty(ITitledDescribedContent['title'])
	description = AdaptingFieldProperty(ITitledDescribedContent['description'])

	def append(self, node):
		name = unicode(len(self))
		self[name] = node

	def updateOrder(self, order):
		raise TypeError("Ordering cannot be changed")

	def __hash__(self):
		# We inherit an __eq__ from dict, but dict does not
		# like to be hashed (because mutable cache keys can be bad)
		# But we have an ACL and need to be hashable
		return hash( tuple(self.items() ) )

	def reset(self):
		keys = list(self)
		for k in keys:
			del self[k]
	clear = reset

@interface.implementer(ICourseOutlineNode)
class CourseOutlineNode(_AbstractCourseOutlineNode,
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
	#_v_nti_pseudo_broken_replacement_name = str('CourseOutlineNode_BROKEN')

	def __setitem__(self, key, value):
		checkObject(self, key, value)
		super(CourseOutlineNode,self).__setitem__(key, value)

	def __delitem__(self, key):
		uncontained(self[key], self, key)
		super(CourseOutlineNode,self).__delitem__(key)

@interface.implementer(ICourseOutlineCalendarNode)
class CourseOutlineCalendarNode(SchemaConfigured,
								CourseOutlineNode):
	createDirectFieldProperties(ICourseOutlineCalendarNode)

	def __init__(self,**kwargs):
		SchemaConfigured.__init__(self,**kwargs)
		CourseOutlineNode.__init__(self)

	AvailableEnding = AdaptingFieldProperty(ICourseOutlineCalendarNode['AvailableEnding'])
	AvailableBeginning = AdaptingFieldProperty(ICourseOutlineCalendarNode['AvailableBeginning'])

@interface.implementer(ICourseOutlineContentNode)
class CourseOutlineContentNode(CourseOutlineCalendarNode):
	createDirectFieldProperties(ICourseOutlineContentNode)

@interface.implementer(ICourseOutline)
class CourseOutline(CourseOutlineNode,
					PersistentCreatedModDateTrackingObject):
	createDirectFieldProperties(ICourseOutline)

	_SET_CREATED_MODTIME_ON_INIT = False
	__external_can_create__ = False

PersistentCourseOutline = CourseOutline

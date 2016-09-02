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

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseOutlineNode

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import IInternalObjectUpdater
from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID

@component.adapter(ICourseOutlineNode)
@interface.implementer(IInternalObjectUpdater)
class _CourseOutlineNodeUpdater(InterfaceObjectIO):

	_ext_iface_upper_bound = ICourseOutlineNode

	@property	
	def node(self):
		return self._ext_self

	def set_ntiid(self, parsed):
		if NTIID.lower() in parsed or NTIID in parsed:
			self.node.ntiid = parsed.get('ntiid') or parsed.get(NTIID)

	def set_locked(self, parsed):
		locked = parsed.get('isLocked')
		if locked and not ICourseOutline.providedBy(self.node):
			self.node.lock()
			
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.set_ntiid(parsed)
		self.set_locked(parsed)
		isPublished = parsed.get('isPublished') # capture param
		result = super(_CourseOutlineNodeUpdater, self).updateFromExternalObject(parsed, *args, **kwargs)
		if ITEMS in parsed:
			for item in parsed.get(ITEMS) or ():
				# parse and update just in case
				if isinstance(item, Mapping):
					factory = find_factory_for(item)
					new_node = factory()
					update_from_external_object(new_node, item, **kwargs)
				else:
					new_node = item
				self.node.append(new_node)
		if 	isPublished \
			and not ICourseOutline.providedBy(self.node) \
			and self.node.publishBeginning is not None:
			self.node.publish()
		return result

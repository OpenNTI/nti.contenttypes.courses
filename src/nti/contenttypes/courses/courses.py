#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from . import interfaces

from nti.dataserver.containers import CaseInsensitiveLastModifiedBTreeFolder
from nti.dataserver.containers import _CheckObjectOnSetMixin

from nti.dataserver.contenttypes.forums.board import GeneralBoard

from zope.cachedescriptors.property import Lazy

_marker = object()

@interface.implementer(interfaces.ICourseAdministrativeLevel)
class CourseAdministrativeLevel(_CheckObjectOnSetMixin,
								CaseInsensitiveLastModifiedBTreeFolder):
	pass

@interface.implementer(interfaces.ICourseInstance)
class CourseInstance(_CheckObjectOnSetMixin,
					 CaseInsensitiveLastModifiedBTreeFolder):

	def __init__(self):
		super(CourseInstance,self).__init__()

	@Lazy
	def Discussions(self):
		self._p_changed = True
		board = GeneralBoard()
		board.__parent__ = self
		board.__name__ = 'Discussions'
		return board

	@property
	def links(self):
		return self._make_links()

	def _make_links(self):
		"""
		Subclasses can extend this to customize the available links.

		"""

		return ()

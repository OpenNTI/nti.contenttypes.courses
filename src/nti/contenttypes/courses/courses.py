#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import lifecycleevent
from zope.cachedescriptors.property import Lazy
from zope.cachedescriptors.property import readproperty

from nti.dataserver.containers import CaseInsensitiveLastModifiedBTreeFolder
from nti.dataserver.containers import _CheckObjectOnSetMixin

from nti.dataserver.contenttypes.forums.board import GeneralBoard

from . import interfaces
from .outlines import CourseOutline
from nti.utils.schema import createDirectFieldProperties

@interface.implementer(interfaces.ICourseAdministrativeLevel)
class CourseAdministrativeLevel(_CheckObjectOnSetMixin,
								CaseInsensitiveLastModifiedBTreeFolder):
	pass

@interface.implementer(interfaces.ICourseInstance)
class CourseInstance(_CheckObjectOnSetMixin,
					 CaseInsensitiveLastModifiedBTreeFolder):

	createDirectFieldProperties(interfaces.ICourseInstance)

	def __init__(self):
		super(CourseInstance,self).__init__()

	# Whether or not they have contents, they are true
	def __bool__(self):
		return True
	__nonzero__ = __bool__

	@Lazy
	def Discussions(self):
		self._p_changed = True
		# Store it inside this folder
		# so it is traversable
		# TODO: Title
		board = GeneralBoard()
		lifecycleevent.created(board)
		self['Discussions'] = board
		return board

	@Lazy
	def Outline(self):
		# As per Discussions
		self._p_changed = True
		outline = CourseOutline()
		lifecycleevent.created(outline)
		self['Outline'] = outline
		return outline

	@readproperty
	def instructors(self):
		return ()

	@property
	def links(self):
		return self._make_links()

	def _make_links(self):
		"""
		Subclasses can extend this to customize the available links.

		"""

		return ()

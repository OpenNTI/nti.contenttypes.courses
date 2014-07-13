#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from . import MessageFactory as _

from zope import interface
from zope import lifecycleevent
from zope.cachedescriptors.property import Lazy
from zope.cachedescriptors.property import readproperty

from nti.contentlibrary.bundle import PersistentContentPackageBundle

from nti.dataserver.containers import CaseInsensitiveCheckingLastModifiedBTreeFolder

from nti.schema.fieldproperty import createDirectFieldProperties

from . import interfaces
from .outlines import CourseOutline
from .sharing import CourseInstanceSharingScopes
from .forum import CourseInstanceBoard

@interface.implementer(interfaces.ICourseAdministrativeLevel)
class CourseAdministrativeLevel(CaseInsensitiveCheckingLastModifiedBTreeFolder):

	pass

@interface.implementer(interfaces.ICourseInstance)
class CourseInstance(CaseInsensitiveCheckingLastModifiedBTreeFolder):

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
		# Course instance boards are a type-of
		# community board, and community boards
		# must be created by a community. We choose
		# the public scope.
		public_scope, = self.SharingScopes.getAllScopesImpliedbyScope('Public')
		board = CourseInstanceBoard()
		board.creator = public_scope
		board.title = _('Discussions')
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

	@Lazy
	def SharingScopes(self):
		# As per Discussions
		self._p_changed = True
		scopes = CourseInstanceSharingScopes()
		lifecycleevent.created(scopes)
		self['SharingScopes'] = scopes
		return scopes

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

from .interfaces import IContentCourseInstance
from nti.contentlibrary.presentationresource import DisplayableContentMixin

@interface.implementer(IContentCourseInstance)
class ContentCourseInstance(DisplayableContentMixin,
							CourseInstance):

	createDirectFieldProperties(IContentCourseInstance)

	@property
	def PlatformPresentationResources(self):
		"""
		If we do not have our own presentation resources,
		and our root is different than our bundle's,
		we return the bundle's resources.
		"""

		ours = super(ContentCourseInstance,self).PlatformPresentationResources
		if ours:
			return ours

		if self.ContentPackageBundle and self.root != self.ContentPackageBundle.root:
			return self.ContentPackageBundle.PlatformPresentationResources

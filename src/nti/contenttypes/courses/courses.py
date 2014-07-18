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

from nti.dataserver.containers import CaseInsensitiveCheckingLastModifiedBTreeFolder
from nti.dataserver.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.schema.fieldproperty import createDirectFieldProperties

from . import interfaces
from .outlines import PersistentCourseOutline
from .sharing import CourseInstanceSharingScopes
from .forum import CourseInstanceBoard

@interface.implementer(interfaces.ICourseAdministrativeLevel)
class CourseAdministrativeLevel(CaseInsensitiveCheckingLastModifiedBTreeFolder):
	pass

@interface.implementer(interfaces.ICourseSubInstances)
class CourseSubInstances(CaseInsensitiveCheckingLastModifiedBTreeContainer):
	pass

@interface.implementer(interfaces.ICourseInstance)
class CourseInstance(CaseInsensitiveCheckingLastModifiedBTreeFolder):
	__external_can_create__ = False
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
		board.createDefaultForum()
		return board

	def _make_Outline(self):
		"""
		A lazy helper to create this object's Outline.
		"""
		# As per Discussions
		self._p_changed = True
		outline = PersistentCourseOutline()
		lifecycleevent.created(outline)
		self['Outline'] = outline
		return outline
	Outline = Lazy(_make_Outline, str('Outline'))

	@Lazy
	def SharingScopes(self):
		# As per Discussions
		self._p_changed = True
		scopes = CourseInstanceSharingScopes()
		lifecycleevent.created(scopes)
		self['SharingScopes'] = scopes
		return scopes

	@Lazy
	def SubInstances(self):
		# As per Discussions
		self._p_changed = True
		folder = CourseSubInstances()
		lifecycleevent.created(folder)
		self['SubInstances'] = folder
		return folder

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
from .interfaces import IContentCourseSubInstance
from Acquisition import aq_acquire
from nti.contentlibrary.presentationresource import DisplayableContentMixin

@interface.implementer(IContentCourseInstance)
class ContentCourseInstance(DisplayableContentMixin,
							CourseInstance):
	__external_class_name__ = 'CourseInstance'
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


@interface.implementer(IContentCourseSubInstance)
class ContentCourseSubInstance(ContentCourseInstance):

	def __getattr__(self, name):
		if name.startswith('_'):
			# TODO: would really like to use the actual
			# acquisition policy
			raise AttributeError(name)
		return aq_acquire(self.__parent__, name)

	@property
	def ContentPackageBundle(self):
		"""
		Our content package bundle is always acquired
		"""
		try:
			return aq_acquire(self.__parent__, 'ContentPackageBundle')
		except AttributeError:
			return None

	def prepare_own_outline(self):
		self._p_activate()
		if 'Outline' not in self.__dict__:
			outline = self._make_Outline()
			self.__dict__[str('Outline')] = outline

	def _get_Outline(self):
		self._p_activate()
		if 'Outline' in self.__dict__:
			return self.__dict__['Outline']
		return aq_acquire(self.__parent__, 'Outline')

	def _set_Outline(self, outline):
		self._p_activate()
		self._p_changed = True
		self.__dict__[str('Outline')] = outline

	def _del_Outline(self):
		self._p_activate()
		if 'Outline' in self.__dict__:
			self._p_changed = True
			del self.__dict__['Outline']

	Outline = property(_get_Outline, _set_Outline, _del_Outline)

	# The original impetus says that they all get separate forums

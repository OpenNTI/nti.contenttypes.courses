#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy
from zope.cachedescriptors.property import readproperty

from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeFolder
from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.contenttypes.courses import MessageFactory as _

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstances
from nti.contenttypes.courses.interfaces import IContentCourseInstance
from nti.contenttypes.courses.interfaces import IContentCourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel

from nti.contenttypes.courses.forum import CourseInstanceBoard

from nti.contenttypes.courses.outlines import CourseOutline

from nti.contenttypes.courses.sharing import CourseInstanceSharingScopes
from nti.contenttypes.courses.sharing import CourseSubInstanceSharingScopes

from nti.schema.fieldproperty import createDirectFieldProperties

@interface.implementer(ICourseAdministrativeLevel)
class CourseAdministrativeLevel(CaseInsensitiveCheckingLastModifiedBTreeFolder):
	pass

@interface.implementer(ICourseSubInstances)
class CourseSubInstances(CaseInsensitiveCheckingLastModifiedBTreeContainer):
	pass

@interface.implementer(ICourseInstance)
class CourseInstance(CaseInsensitiveCheckingLastModifiedBTreeFolder):
	__external_can_create__ = False
	createDirectFieldProperties(ICourseInstance)

	lastSynchronized = 0

	def __init__(self):
		super(CourseInstance, self).__init__()

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
		scopes = self.SharingScopes
		scopes.initScopes()
		public_scope = scopes[ES_PUBLIC]

		board = CourseInstanceBoard()
		board.creator = public_scope
		board.title = _('Discussions')
		lifecycleevent.created(board)
		self['Discussions'] = board
		board.createDefaultForum()
		return board

	def _delete_Outline(self):
		result = False
		for m in (self.__dict__, self):
			try:
				del m['Outline']
				result = True
			except KeyError:
				pass
		return result

	def _make_Outline(self):
		"""
		A lazy helper to create this object's Outline.
		"""
		# As per Discussions
		self._p_changed = True
		outline = CourseOutline()
		lifecycleevent.created(outline)
		try:
			self['Outline'] = outline
		except KeyError:
			logger.error("Cannot set outline for %s", self.__name__)
			raise
		return outline
	Outline = Lazy(_make_Outline, str('Outline'))

	@Lazy
	def SharingScopes(self):
		# As per Discussions
		self._p_changed = True
		scopes = self._make_sharing_scopes()
		lifecycleevent.created(scopes)
		self['SharingScopes'] = scopes
		return scopes

	def _make_sharing_scopes(self):
		return CourseInstanceSharingScopes()

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

		ours = super(ContentCourseInstance, self).PlatformPresentationResources
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

	def _make_sharing_scopes(self):
		return CourseSubInstanceSharingScopes()

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

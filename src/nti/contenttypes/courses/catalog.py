#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementations of course catalogs.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from functools import total_ordering

from zope import interface

from .interfaces import ICourseInstance

from nti.contentlibrary.presentationresource import DisplayableContentMixin

from nti.dataserver.links import Link
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME
from nti.dataserver.containers import CheckingLastModifiedBTreeContainer
from nti.dataserver.containers import CheckingLastModifiedBTreeFolder

from nti.externalization.persistence import NoPickle
from nti.externalization.externalization import WithRepr

from nti.schema.schema import EqHash
from nti.schema.fieldproperty import createDirectFieldProperties
from nti.schema.schema import PermissiveSchemaConfigured as SchemaConfigured

from nti.utils.property import alias
from nti.utils.property import readproperty
from nti.utils.property import LazyOnClass
from zope.cachedescriptors.method import cachedIn

from nti.dublincore.time_mixins import CreatedAndModifiedTimeMixin

from .interfaces import IGlobalCourseCatalog
from .interfaces import IPersistentCourseCatalog
from .interfaces import ICourseCatalog
from .interfaces import ICourseCatalogEntry
from .interfaces import ICourseCatalogInstructorInfo

from nti.site.localutility import queryNextUtility

def _queryNextCatalog(context):
	return queryNextUtility(context,ICourseCatalog)

class _AbstractCourseCatalogMixin(object):
	"""
	Defines the interface methods for a generic course
	catalog, including tree searching.
	"""

	__name__ = 'CourseCatalog'

	@LazyOnClass
	def __acl__( self ):
		# Got to be here after the components are registered
		return acl_from_aces(
			# Everyone logged in has read and search access to the catalog
			ace_allowing(AUTHENTICATED_GROUP_NAME, ACT_READ, type(self) ) )

	# regardless of length, catalogs are True
	def __bool__(self):
		return True
	__nonzero__ = __bool__

	@property
	def _next_catalog(self):
		return _queryNextCatalog(self)

	def _get_all_my_entries(self):
		"Return all the entries at this level"
		raise NotImplementedError()

	def isEmpty(self):
		# TODO: should this be in the hierarchy?
		return not self._get_all_my_entries()

	def iterCatalogEntries(self):
		entries = {e.ntiid: e for e in self._get_all_my_entries()}

		parent = self._next_catalog
		if parent is not None:
			for e in parent.iterCatalogEntries():
				if e.ntiid not in entries:
					entries[e.ntiid] = e

		return list(entries.values())

	def _primary_query_my_entry(self, name):
		for entry in self._get_all_my_entries():
			if name == entry.ntiid:
				return entry

	def _fallback_query_my_entry(self, name):
		# Ok, is it asking by name, during traversal?
		# This is a legacy case that shouldn't be hit anymore,
		# except during tests that are hardcoded.

		for entry in self._get_all_my_entries():
			if entry.ProviderUniqueID == name:
				logger.warning("Using legacy ProviderUniqueID to match %s to %s",
							   name, entry)
				return entry

	def _query_my_entry(self, name):
		entry = self._primary_query_my_entry(name)
		if entry is None:
			entry = self._fallback_query_my_entry(name)
		return entry

	def getCatalogEntry(self, name):
		entry = self._query_my_entry(name)
		if entry is not None:
			return entry

		parent = self._next_catalog
		if parent is None:
			raise KeyError(name)

		return parent.getCatalogEntry(name)



@interface.implementer(IGlobalCourseCatalog)
@NoPickle
@WithRepr
class GlobalCourseCatalog(_AbstractCourseCatalogMixin,
						  CheckingLastModifiedBTreeContainer):

	# NOTE: We happen to inherit Persistent, which we really
	# don't want.

	lastModified = 0

	def _get_all_my_entries(self):
		return list(self.values())

	def _primary_query_my_entry(self, name):
		try:
			return CheckingLastModifiedBTreeContainer.__getitem__(self, name)
		except KeyError:
			return None

	def addCatalogEntry(self, entry, event=True):
		"""
		Adds an entry to this catalog.

		:keyword bool event: If true (the default), we broadcast
			the object added event.
		"""
		key = entry.ntiid or entry.__name__
		if not key:
			raise ValueError(entry)
		if CheckingLastModifiedBTreeContainer.__contains__(self, key):
			if entry.__parent__ is self:
				return
			raise ValueError("Adding duplicate entry %s", entry)

		if event:
			self[key] = entry
		else:
			self._setitemf(key, entry)
			entry.__parent__ = self

		self.lastModified = max( self.lastModified, entry.lastModified )


	append = addCatalogEntry

	def removeCatalogEntry(self, entry, event=True):
		"""
		Remove an entry from this catalog.

		:keyword bool event: If true (the default), we broadcast
			the object removed event.
		"""
		key = entry.ntiid or entry.__name__
		__traceback_info__ = key, entry
		if not event:
			l = self._BTreeContainer__len
			try:
				entry = self._SampleContainer__data[key]
				del self._SampleContainer__data[key]
				l.change(-1)
				entry.__parent__ = None
			except KeyError:
				pass
		else:
			if CheckingLastModifiedBTreeContainer.__contains__(self, key):
				del self[key]

	def isEmpty(self):
		# we can be more efficient than the parent
		return len(self) == 0

	def clear(self):
		for i in list(self.iterCatalogEntries()):
			self.removeCatalogEntry(i, event=False)

	def __contains__(self, ix):
		if CheckingLastModifiedBTreeContainer.__contains__(self, ix):
			return True

		try:
			return self[ix] is not None
		except KeyError:
			return False

	__getitem__ = _AbstractCourseCatalogMixin.getCatalogEntry


@interface.implementer(ICourseCatalogInstructorInfo)
@WithRepr
class CourseCatalogInstructorInfo(SchemaConfigured):
	createDirectFieldProperties(ICourseCatalogInstructorInfo)

@interface.implementer(ICourseCatalogEntry)
@WithRepr
@total_ordering
@EqHash('ntiid')
class CourseCatalogEntry(SchemaConfigured,
						 DisplayableContentMixin,
						 CreatedAndModifiedTimeMixin):
	# shut up pylint
	ntiid = None
	StartDate = None
	Duration = None

	_SET_CREATED_MODTIME_ON_INIT = False

	createDirectFieldProperties(ICourseCatalogEntry)

	__name__ = alias('ntiid')
	__parent__ = None

	# legacy compatibility
	Title = alias('title')
	Description = alias('description')

	def __init__(self, *args, **kwargs):
		SchemaConfigured.__init__(self, *args, **kwargs) # not cooperative
		CreatedAndModifiedTimeMixin.__init__(self)

	def __lt__(self, other):
		return self.ntiid < other.ntiid

	@property
	def links(self):
		return self._make_links()

	def _make_links(self):
		"""
		Subclasses can extend this to customize the available links.

		If we are adaptable to a :class:`.ICourseInstance`, we
		produce a link to that.
		"""
		result = []
		instance = ICourseInstance(self, None)
		if instance:
			result.append( Link( instance, rel="CourseInstance" ) )

		return result

	@property
	def PlatformPresentationResources(self):
		"""
		If we do not have a set of presentation assets,
		we echo the first thing we have that does contain
		them. This should simplify things for the clients.
		"""
		ours = super(CourseCatalogEntry,self).PlatformPresentationResources
		if ours:
			return ours

		# Ok, do we have a course, and if so, does it have
		# a bundle or legacy content package?
		theirs = None
		try:
			course = ICourseInstance(self, None)
		except LookupError:
			# typically outside af a transaction
			course = None
		if course is None:
			# we got nothing
			return

		# Does it have a bundle with resources?
		try:
			theirs = course.ContentPackageBundle.PlatformPresentationResources
		except AttributeError:
			pass

		if theirs:
			return theirs

		# Does it have the old legacy property?
		try:
			theirs = course.legacy_content_package.PlatformPresentationResources
		except AttributeError:
			pass

		return theirs

	@readproperty
	def InstructorsSignature(self):
		sig_lines = []
		for inst in self.Instructors:
			sig_lines.append( inst.Name )
			sig_lines.append( inst.JobTitle )

			sig_lines.append( "" )
		del sig_lines[-1] # always at least one instructor. take off the last trailing line
		signature = '\n\n'.join( sig_lines )
		return signature


@interface.implementer(IPersistentCourseCatalog)
class CourseCatalogFolder(_AbstractCourseCatalogMixin,
						  CheckingLastModifiedBTreeFolder):
	"""
	A folder whose contents are (recursively) the course instances
	for which we will generate the appropriate course catalog entries
	as needed.

	This folder is intended to be registered as a utility providing
	:class:`ICourseCatalog`. It cooperates with utilities higher
	in parent sites.

	.. note:: Although currently the catalog is flattened,
		in the future the folder structure might mean something
		(e.g., be incorporated into the workspace structure at the
		application level).
	"""

	@cachedIn('_v_all_my_entries')
	def _get_all_my_entries(self):
		# TODO: invalidation?
		# At least we can do method.invalidate
		entries = list()

		def _recur(folder):
			course = ICourseInstance(folder, None)
			if course:
				entry = ICourseCatalogEntry(course, None)
				if entry:
					entries.append(entry)
					for subinstance in course.SubInstances.values():
						entry = ICourseCatalogEntry(subinstance, None)
						if entry:
							entries.append(entry)
				# We don't need to go any deeper than two levels
				# (If we hit the community members in the scope, we
				# can get infinite recursion)
				return
			try:
				folder_values = folder.values()
			except AttributeError:
				pass
			else:
				for value in folder_values:
					_recur(value)
		_recur(self)
		return entries

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Legacy extensions to the catalog.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from datetime import datetime

from zope import interface
from zope import component

from nti.common.property import readproperty

from nti.schema.field import Int
from nti.schema.field import Dict
from nti.schema.field import List
from nti.schema.field import Bool
from nti.schema.field import Object
from nti.schema.field import ValidURI
from nti.schema.field import ValidTextLine
from nti.schema.schema import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from .interfaces import ICourseCatalog
from .interfaces import ICourseCatalogEntry
from .interfaces import ICourseCatalogInstructorInfo

from .catalog import CourseCatalogEntry
from .catalog import CourseCatalogInstructorInfo

class ICourseCatalogInstructorLegacyInfo(ICourseCatalogInstructorInfo):
	"""
	Additional legacy info about course instructors.
	"""

	defaultphoto = ValidTextLine(title="A URL path for an extra copy of the instructor's photo",
								 description="ideally this should be the profile photo",
								 default='',
								 required=False) # TODO: We need a schema field for this

	username = ValidTextLine(title="A username string that may or may not refer to an actual account.",
							 default='',
							 required=True)
	username.setTaggedValue('_ext_excluded_out', True) # Internal use only

class ICourseCreditLegacyInfo(interface.Interface):
	"""
	Describes how academic credit can be obtained
	for this course.

	"""

	Hours = Int(title="The number of hours that can be earned.",
					   min=1)
	Enrollment = Dict(title="Information about how to enroll. This is not modeled.",
					  key_type=ValidTextLine(title="A key"),
					  value_type=ValidTextLine(title="A value"))


class ICourseCatalogLegacyEntry(ICourseCatalogEntry):
	"""
	Adds information used by or provided from legacy sources.

	Most of this is unmodeled content that the server doesn't interpret.

	A decorator should add a `ContentPackageNTIID` property
	if possible.
	"""

	# Legacy. This isn't really part of the course catalog.
	# Nothing seems to use it anyway
	#Communities = ListOrTuple(value_type=TextLine(title='The community'),
	#						  title="Course communities",
	#						  required=False)

	# While this might be a valid part of the course catalog, this
	# representation of it isn't very informative or flexible
	Credit = List(value_type=Object(ICourseCreditLegacyInfo),
				  title="Either missing or an array with one entry.",
				  required=False)

	Video = ValidURI(title="A URL-like string, possibly using private-but-un-prefixed schemes, or the empty string or missing.",
					 required=False)

	Schedule = Dict(title="An unmodeled dictionary, possibly useful for presentation.")

	Prerequisites = List(title="A list of dictionaries suitable for presentation. Expect a `title` key.",
						 value_type=Dict(key_type=ValidTextLine(),
										 value_type=ValidTextLine()))

	Preview = Bool(title="Is this entry for a course that is upcoming?",
				   description="This course should be considered an advertising preview"
				   " and not yet have its content accessed.")


	DisableOverviewCalendar = Bool(title="A URL or path of indeterminate type or meaning",
								   required=False, default=False)

	###
	# These are being replaced with presentation specific asset bundles
	# (one path is insufficient to handle things like retina displays
	# and the various platforms).
	###
	LegacyPurchasableIcon = ValidTextLine(title="A URL or path of indeterminate type or meaning",
									 required=False)

	LegacyPurchasableThumbnail = ValidTextLine(title="A URL or path of indeterminate type or meaning",
										  required=False)

# Legacy extensions

@interface.implementer(ICourseCreditLegacyInfo)
class CourseCreditLegacyInfo(SchemaConfigured):
	createDirectFieldProperties(ICourseCreditLegacyInfo)
	__external_can_create__ = False

@interface.implementer(ICourseCatalogInstructorLegacyInfo)
class CourseCatalogInstructorLegacyInfo(CourseCatalogInstructorInfo):
	defaultphoto = None
	__external_can_create__ = False
	createDirectFieldProperties(ICourseCatalogInstructorLegacyInfo)

def _derive_preview(self):
	if self.StartDate is not None:
		return self.StartDate > datetime.utcnow()

@interface.implementer(ICourseCatalogLegacyEntry)
class CourseCatalogLegacyEntry(CourseCatalogEntry):
	DisableOverviewCalendar = False
	__external_can_create__ = False
	createDirectFieldProperties(ICourseCatalogLegacyEntry)

	#: For legacy catalog entries created from a content package,
	#: this will be that package (an implementation of
	#: :class:`.ILegacyCourseConflatedContentPackage`)
	#legacy_content_package = None

	@readproperty
	def EndDate(self):
		"""
		We calculate the end date based on the duration and the start
		date, if possible. Otherwise, None.
		"""
		if self.StartDate is not None and self.Duration is not None:
			return self.StartDate + self.Duration

	@readproperty
	def Preview(self):
		"""
		If a preview hasn't been specifically set, we derive it
		if possible.
		"""
		return _derive_preview(self)

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.externalization.representation import WithRepr

# The objects we're going to be containing we *assume* live somewhere beneath
# an object that implements course catalog (folder). We automatically derive
# ntiids from that structure.

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import make_specific_safe

def _ntiid_from_entry(entry, nttype='CourseInfo'):
	parents = []
	o = entry.__parent__
	while o is not None and not ICourseCatalog.providedBy(o):
		parents.append(o.__name__)
		o = getattr(o, '__parent__', None)

	parents.reverse()
	if None in parents:
		# Have seen this in alpha...possibly due to mutating content?
		logger.warn("Unable to get ntiid for %r, missing parents: %r",
					entry, parents)
		return None

	relative_path = '/'.join(parents)
	if not relative_path:
		return None

	ntiid = make_ntiid(provider='NTI',
					   nttype=nttype,
					   specific=make_specific_safe(relative_path))
	return ntiid

from nti.common.property import CachedProperty

class PersistentCourseCatalogLegacyEntry(CourseCatalogLegacyEntry,
										 PersistentCreatedAndModifiedTimeObject):

	def __init__(self, *args, **kwargs):
		# Schema configured is not cooperative
		CourseCatalogLegacyEntry.__init__(self, *args, **kwargs)
		PersistentCreatedAndModifiedTimeObject.__init__(self)

	@CachedProperty('__parent__')
	def _cached_ntiid(self):
		return _ntiid_from_entry(self)

	ntiid = property(lambda s: s._cached_ntiid,
					 lambda s, nv: None)

from zope.annotation.factory import factory as an_factory

from nti.schema.schema import EqHash

from nti.traversal.traversal import find_interface

from .interfaces import ICourseInstance

@component.adapter(ICourseInstance)
class _CourseInstanceCatalogLegacyEntry(PersistentCourseCatalogLegacyEntry):
	__external_class_name__ = 'CourseCatalogLegacyEntry'
	__external_can_create__ = False

	# Because we're used in an annotation, the parent's attempt
	# to alias ntiid to __name__ gets basically ignored: the return
	# value from the annotation factory is always proxied to have
	# a name equal to the key
	__name__ = None

	def __conform__(self, iface):
		return find_interface(self, iface, strict=False)

CourseInstanceCatalogLegacyEntryFactory = an_factory(_CourseInstanceCatalogLegacyEntry,
													 key='CourseCatalogEntry')

from functools import total_ordering

from zope.container.contained import Contained

from nti.contentlibrary.presentationresource import DisplayableContentMixin

from nti.dataserver.links import Link

from .interfaces import ICourseSubInstance

@component.adapter(ICourseSubInstance)
@interface.implementer(ICourseCatalogLegacyEntry)
@WithRepr
@total_ordering
@EqHash('ntiid')
class _CourseSubInstanceCatalogLegacyEntry(Contained,
										   DisplayableContentMixin,
										   PersistentCreatedAndModifiedTimeObject):
	"""
	The entry for a sub-instance is writable, but
	any value it does not have it inherits from
	the closest parent.

	We always maintain our own created and modification dates, though.
	"""
	__external_class_name__ = 'CourseCatalogLegacyEntry'
	__external_can_create__ = False

	_SET_CREATED_MODTIME_ON_INIT = False # default to 0

	def __lt__(self, other):
		return self.ntiid < other.ntiid

	ntiid = property(_ntiid_from_entry,
					 lambda s, nv: None)

	@property
	def links(self):
		"""
		If we are adaptable to a :class:`.ICourseInstance`, we
		produce a link to that.
		"""
		# Note we're not inheriting from self._next_entry here
		result = ()
		instance = ICourseInstance(self, None)
		if instance is not None:
			result = [Link( instance, rel="CourseInstance" )]
		return result

	@property
	def PlatformPresentationResources(self):
		ours = super(_CourseSubInstanceCatalogLegacyEntry,self).PlatformPresentationResources
		if ours:
			return ours
		return self._next_entry.PlatformPresentationResources

	@readproperty
	def Preview(self):
		# Our preview status can be explicitly set; if it's not set
		# (only circumstance we'd get called), and we explicitly have
		# a start date, then we want to use that; otherwise we want to
		# inherit as normal
		self._p_activate()

		if 'StartDate' in self.__dict__: # whether or not its None
			return _derive_preview(self)

		return getattr(self._next_entry, 'Preview', None)

	def isCourseCurrentlyActive(self):
		# XXX: duplicated from the main catalog entry
		if getattr(self, 'Preview', False):
			# either manually set, or before the start date
			# some objects don't have this flag at all
			return False
		# we've seen these with no actual _next_entry, meaning
		# attribute access can raise (how'd that happen?)
		if getattr(self, 'EndDate', None):
			# if we end in the future we're active
			return self.EndDate > datetime.utcnow()
		# otherwise, with no information given, assume
		# we're active
		return True

	@readproperty
	def _next_instance(self):
		# recall our parent is the ICourseSubInstance, we want to walk
		# up from there.
		try:
			pp = self.__parent__.__parent__
		except AttributeError:
			# no parent
			return None
		else:
			return find_interface(pp, ICourseInstance, strict=False)

	@readproperty
	def _next_entry(self):
		return ICourseCatalogEntry(self._next_instance, None)

	def __getattr__(self, key):
		# We don't have it. Does our parent?
		if key.startswith('_'):
			# TODO: would really like to use the actual
			# acquisition policy
			raise AttributeError(key)

		return getattr(self._next_entry, key)


	def __conform__(self, iface):
		return find_interface(self, iface, strict=False)

CourseSubInstanceCatalogLegacyEntryFactory = an_factory(_CourseSubInstanceCatalogLegacyEntry,
														key='CourseCatalogEntry')

# For externalization of the interfaces defined in this module,
# which does not fit the traditional pattern

from zope.dottedname import resolve as dottedname

class _LegacyCatalogAutoPackageSearchingScopedInterfaceObjectIO(object):

	@classmethod
	def _ap_find_package_interface_module(cls):
		return dottedname.resolve('nti.contenttypes.courses.legacy_catalog')

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Legacy extensions to the catalog.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

###
# Legacy interface Extensions
###

from .interfaces import ICourseCatalogInstructorInfo
from .interfaces import ICourseCatalogEntry

from nti.schema.field import ValidTextLine
from nti.schema.field import Int
from nti.schema.field import Dict
from nti.schema.field import List
from nti.schema.field import ValidURI
from nti.schema.field import Bool
from nti.schema.field import Object

from nti.schema.fieldproperty import createDirectFieldProperties
from nti.schema.schema import SchemaConfigured

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

@interface.implementer(ICourseCatalogInstructorLegacyInfo)
class CourseCatalogInstructorLegacyInfo(CourseCatalogInstructorInfo):
	defaultphoto = None
	createDirectFieldProperties(ICourseCatalogInstructorLegacyInfo)

from nti.utils.property import readproperty
import datetime

@interface.implementer(ICourseCatalogLegacyEntry)
class CourseCatalogLegacyEntry(CourseCatalogEntry):
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
		if self.StartDate is not None:
			return self.StartDate > datetime.datetime.utcnow()

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject
from persistent import Persistent

class PersistentCourseCatalogLegacyEntry(CourseCatalogLegacyEntry,
										 PersistentCreatedAndModifiedTimeObject):

	def __init__(self, *args, **kwargs):
		# Schema configured is not cooperative
		CourseCatalogLegacyEntry.__init__(self, *args, **kwargs)
		PersistentCreatedAndModifiedTimeObject.__init__(self)


from zope.annotation.factory import factory as an_factory
from nti.dataserver.traversal import find_interface
from .interfaces import ICourseInstance

@component.adapter(ICourseInstance)
class _CourseInstanceCatalogLegacyEntry(PersistentCourseCatalogLegacyEntry):

	def __conform__(self, iface):
		return find_interface(self, iface, strict=False)

CourseInstanceCatalogLegacyEntryFactory = an_factory(_CourseInstanceCatalogLegacyEntry)

from .interfaces import ICourseSubInstance
from zope.container.contained import Contained

@component.adapter(ICourseSubInstance)
@interface.implementer(ICourseCatalogLegacyEntry)
class _CourseSubInstanceCatalogLegacyEntry(Contained,Persistent):
	"""
	The entry for a sub-instance is writable, but
	any value it does not have it inherits from
	the closest parent.
	"""

	@readproperty
	def _next_instance(self):
		# recall our parent is the ICourseSubInstance, we want to walk
		# up from there.
		return find_interface(self.__parent__.__parent__, ICourseInstance, strict=False)

	@readproperty
	def _next_entry(self):
		return ICourseCatalogEntry(self._next_instance, None)

	def __getattr__(self, key):
		# We don't have it. Does our parent?
		return getattr(self._next_entry, key)

	def __conform__(self, iface):
		return find_interface(self, iface, strict=False)

CourseSubInstanceCatalogLegacyEntryFactory = an_factory(_CourseSubInstanceCatalogLegacyEntry)

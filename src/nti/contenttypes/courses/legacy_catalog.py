#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Legacy extensions to the catalog.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class

from Acquisition import aq_acquire

from Persistence import Persistent

from datetime import datetime

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy
from zope.cachedescriptors.property import readproperty

from nti.contenttypes.courses.catalog import CourseCatalogEntry
from nti.contenttypes.courses.catalog import CourseCatalogInstructorInfo

from nti.contenttypes.courses.interfaces import NTIID_ENTRY_TYPE
from nti.contenttypes.courses.interfaces import NTIID_ENTRY_PROVIDER

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseCatalogInstructorInfo

from nti.contenttypes.courses.utils import path_for_entry

from nti.externalization.representation import WithRepr

from nti.property.property import alias

from nti.recorder.mixins import RecordableMixin

from nti.schema.field import Int
from nti.schema.field import Dict
from nti.schema.field import List
from nti.schema.field import Bool
from nti.schema.field import Object
from nti.schema.field import ValidURI
from nti.schema.field import ValidTextLine

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

logger = __import__('logging').getLogger(__name__)


class ICourseCatalogInstructorLegacyInfo(ICourseCatalogInstructorInfo):
    """
    Additional legacy info about course instructors.
    """

    defaultphoto = ValidTextLine(title=u"A URL path for an extra copy of the instructor's photo",
                                 description=u"ideally this should be the profile photo",
                                 default=u'',
                                 required=False)  # We need a schema field for this

    username = ValidTextLine(title=u"A username string that may or may not refer to an actual account.",
                             default=u'',
                             required=True)

    userid = ValidTextLine(title=u"A username string that may or may not refer to an actual account.",
                           default=u'',
                           required=False)


class ICourseCreditLegacyInfo(interface.Interface):
    """
    Describes how academic credit can be obtained
    for this course.

    """

    Hours = Int(title=u"The number of hours that can be earned.",
                default=0,
                min=0)

    Enrollment = Dict(title=u"Information about how to enroll. This is not modeled.",
                      key_type=ValidTextLine(title=u"A key"),
                      value_type=ValidTextLine(title=u"A value"))


class ICourseCatalogLegacyEntry(ICourseCatalogEntry):
    """
    Adds information used by or provided from legacy sources.

    Most of this is unmodeled content that the server doesn't interpret.

    A decorator should add a `ContentPackageNTIID` property if possible.
    """

    # While this might be a valid part of the course catalog, this
    # representation of it isn't very informative or flexible
    Credit = List(value_type=Object(ICourseCreditLegacyInfo),
                  title=u"Either missing or an array with one entry.",
                  required=False)

    Video = ValidURI(title=u"A URL-like string, possibly using private-but-un-prefixed schemes, "
                     u"or the empty string or missing.",
                     required=False)

    Schedule = Dict(title=u"An unmodeled dictionary, possibly useful for presentation.",
                    required=False)

    Prerequisites = List(title=u"A list of dictionaries suitable for presentation. Expect a `title` key.",
                         value_type=Dict(key_type=ValidTextLine(),
                                         value_type=ValidTextLine()),
                         required=False)

    Preview = Bool(title=u"Is this entry for a course that is upcoming?",
                   description=u"This course should be considered an advertising preview "
                   u"and not yet have its content accessed.")

    DisableOverviewCalendar = Bool(title=u"A URL or path of indeterminate type or meaning",
                                   required=False,
                                   default=False)

    # These are being replaced with presentation specific asset bundles
    # (one path is insufficient to handle things like retina displays
    # and the various platforms).
    LegacyPurchasableIcon = ValidTextLine(title=u"A URL or path of indeterminate type or meaning",
                                          required=False)

    LegacyPurchasableThumbnail = ValidTextLine(title=u"A URL or path of indeterminate type or meaning",
                                               required=False)


# Legacy extensions


@WithRepr
@interface.implementer(ICourseCreditLegacyInfo)
class CourseCreditLegacyInfo(SchemaConfigured):
    createDirectFieldProperties(ICourseCreditLegacyInfo)


@interface.implementer(ICourseCatalogInstructorLegacyInfo)
class CourseCatalogInstructorLegacyInfo(CourseCatalogInstructorInfo):
    createDirectFieldProperties(ICourseCatalogInstructorLegacyInfo)

    Email = None
    Biography = None
    defaultphoto = None

    email = alias('Email')
    Bio = alias('Biography')


def _derive_preview(self):
    if self.StartDate is not None:
        return self.StartDate > datetime.utcnow()
    return False


@interface.implementer(ICourseCatalogLegacyEntry)
class CourseCatalogLegacyEntry(CourseCatalogEntry):
    createDirectFieldProperties(ICourseCatalogLegacyEntry)

    creators = ()
    DisableOverviewCalendar = False

    # For legacy catalog entries created from a content package,
    # this will be that package (an implementation of
    # :class:`.ILegacyCourseConflatedContentPackage`)
    # legacy_content_package = None

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

    @property
    def PreviewRawValue(self):
        # pylint: disable=no-member
        self._p_activate()
        return self.__dict__.get('Preview', None)


from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

# The objects we're going to be containing we *assume* live somewhere beneath
# an object that implements course catalog (folder). We automatically derive
# ntiids from that structure.

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import make_specific_safe


def _ntiid_from_entry(entry, nttype=NTIID_ENTRY_TYPE):
    relative_path = path_for_entry(entry)
    if not relative_path:
        return None
    ntiid = make_ntiid(provider=NTIID_ENTRY_PROVIDER,
                       nttype=nttype,
                       specific=make_specific_safe(relative_path))
    return ntiid


class PersistentCourseCatalogLegacyEntry(CourseCatalogLegacyEntry,
                                         PersistentCreatedAndModifiedTimeObject,
                                         RecordableMixin):

    # pylint: disable=super-init-not-called
    def __init__(self, *args, **kwargs):
        # Schema configured is not cooperative
        CourseCatalogLegacyEntry.__init__(self, *args, **kwargs)
        PersistentCreatedAndModifiedTimeObject.__init__(self)

    @Lazy
    def ntiid(self):
        return _ntiid_from_entry(self)


from zope.annotation.factory import factory as an_factory

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.schema.eqhash import EqHash

from nti.traversal.traversal import find_interface


@component.adapter(ICourseInstance)
class _CourseInstanceCatalogLegacyEntry(PersistentCourseCatalogLegacyEntry):
    __external_can_create__ = False
    __external_class_name__ = 'CourseCatalogLegacyEntry'

    # Because we're used in an annotation, the parent's attempt
    # to alias ntiid to __name__ gets basically ignored: the return
    # value from the annotation factory is always proxied to have
    # a name equal to the key
    __name__ = None

    def __conform__(self, iface):
        return find_interface(self, iface, strict=False)


CourseInstanceCatalogLegacyEntryFactory = an_factory(_CourseInstanceCatalogLegacyEntry,
                                                     key=u'CourseCatalogEntry')

from functools import total_ordering

from zope.container.contained import Contained

from nti.contentlibrary.presentationresource import DisplayableContentMixin

from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.links.links import Link


@WithRepr
@total_ordering
@EqHash('ntiid')
@component.adapter(ICourseSubInstance)
@interface.implementer(ICourseCatalogLegacyEntry)
class _CourseSubInstanceCatalogLegacyEntry(Persistent,
                                           Contained,
                                           DisplayableContentMixin,
                                           PersistentCreatedAndModifiedTimeObject):
    """
    The entry for a sub-instance is writable, but any value it does not have
    it inherits from the closest parent.

    We always maintain our own created and modification dates, though.
    """
    __external_class_name__ = 'CourseCatalogLegacyEntry'
    __external_can_create__ = False

    _SET_CREATED_MODTIME_ON_INIT = False  # default to 0

    def __lt__(self, other):
        return self.ntiid < other.ntiid

    ntiid = property(_ntiid_from_entry,
                     lambda unused_s, unused_nv: None)

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
            result = [Link(instance, rel="CourseInstance")]
        return result

    @property
    def PlatformPresentationResources(self):
        ours = super(_CourseSubInstanceCatalogLegacyEntry, self).PlatformPresentationResources
        if ours:  # pylint: disable=using-constant-test
            return ours
        # pylint: disable=no-member
        return self._next_entry.PlatformPresentationResources

    @readproperty
    def Preview(self):
        # Our preview status can be explicitly set; if it's not set
        # (only circumstance we'd get called), and we explicitly have
        # a start date, then we want to use that; otherwise we want to
        # inherit as normal
        self._p_activate()
        if 'StartDate' in self.__dict__:  # whether or not its None
            return _derive_preview(self)
        return getattr(self._next_entry, 'Preview', False)

    @property
    def PreviewRawValue(self):
        self._p_activate()
        return self.__dict__.get('Preview', None)

    def isCourseCurrentlyActive(self):
        # duplicated from the main catalog entry
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
    
    def _get_seat_limit(self):
        self._p_activate()
        if 'seat_limit' in self.__dict__:
            return self.__dict__['seat_limit']
        return aq_acquire(self._next_entry, 'seat_limit').__of__(self)

    def _set_seat_limit(self, seat_limit):
        self._p_activate()
        self._p_changed = True
        if seat_limit is not None:
            seat_limit.__parent__ = self
        self.__dict__['seat_limit'] = seat_limit

    def _del_seat_limit(self):
        self._p_activate()
        if 'seat_limit' in self.__dict__:
            self._p_changed = True
            del self.__dict__['seat_limit']

    seat_limit = property(_get_seat_limit, _set_seat_limit, _del_seat_limit)

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
            # Would really like to use the actual
            # acquisition policy
            raise AttributeError(key)
        return getattr(self._next_entry, key)

    def __conform__(self, iface):
        return find_interface(self, iface, strict=False)


CourseSubInstanceCatalogLegacyEntryFactory = an_factory(_CourseSubInstanceCatalogLegacyEntry,
                                                        key=u'CourseCatalogEntry')

# For externalization of the interfaces defined in this module,
# which does not fit the traditional pattern

from zope.dottedname import resolve as dottedname


class _LegacyCatalogAutoPackageSearchingScopedInterfaceObjectIO(object):

    @classmethod
    def _ap_find_package_interface_module(cls):
        return dottedname.resolve('nti.contenttypes.courses.legacy_catalog')


# legacy course


class ILegacyCourseCatalogEntry(ICourseCatalogLegacyEntry):
    """
    Marker interface for a legacy course catalog entry
    """


class ILegacyCourseInstance(ICourseInstance):
    """
    Marker interface for a legacy course instance
    """

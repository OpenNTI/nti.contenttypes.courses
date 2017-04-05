#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time

from collections import namedtuple

from zope import interface

from zope.catalog.interfaces import ICatalog

from zope.component.hooks import getSite

from zope.deprecation import deprecated

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.base._compat import unicode_

from nti.contenttypes.courses.common import get_course_site
from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseKeywords
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineCalendarNode
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.zope_catalog.catalog import Catalog

from nti.zope_catalog.datetime import TimestampToNormalized64BitIntNormalizer

from nti.zope_catalog.index import AttributeSetIndex
from nti.zope_catalog.index import NormalizationWrapper
from nti.zope_catalog.index import AttributeKeywordIndex
from nti.zope_catalog.index import SetIndex as RawSetIndex
from nti.zope_catalog.index import AttributeValueIndex as ValueIndex
from nti.zope_catalog.index import IntegerValueIndex as RawIntegerValueIndex


# Deprecations


deprecated('ValidatingUsernameID', 'Use latest index implementation')
class ValidatingUsernameID(object):

    def __init__(self, *args, **kwargs):
        pass


deprecated('SiteIndex', 'Replaced with SingleSiteIndex')
class SiteIndex(RawSetIndex):
    pass


deprecated('ScopeIndex', 'Replaced with ScopeSetIndex')
class ScopeIndex(ValueIndex):
    pass


deprecated('ValidatingScope', 'Use new implementation')
class ValidatingScope(object):
    pass


# Utilities


class KeepSetIndex(RawSetIndex):

    empty_set = set()

    def to_iterable(self, value):
        return value

    def index_doc(self, doc_id, value):
        value = {v for v in self.to_iterable(value) if v is not None}
        current = self.documents_to_values.get(doc_id) or self.empty_set
        if value.difference(current):
            value.update(current)
            return super(KeepSetIndex, self).index_doc(doc_id, value)

    def remove(self, doc_id, value):
        current = set(self.documents_to_values.get(doc_id) or ())
        if not current:
            return
        for v in self.to_iterable(value):
            current.discard(v)
        if current:
            return super(KeepSetIndex, self).index_doc(doc_id, current)
        return super(KeepSetIndex, self).unindex_doc(doc_id)


# Enrollment catalog


IndexRecord = namedtuple('IndexRecord', 'username ntiid Scope')

ENROLLMENT_CATALOG_NAME = 'nti.dataserver.++etc++enrollment-catalog'

IX_SITE = 'site'
IX_SCOPE = 'scope'
IX_CREATEDTIME = 'createdTime'
IX_ENTRY = IX_COURSE = 'course'
IX_LASTMODIFIED = 'lastModified'
IX_USERNAME = IX_STUDENT = IX_INSTRUCTOR = 'username'


class ValidatingSiteName(object):

    __slots__ = (b'site',)

    def __init__(self, obj, default=None):
        # For value indexes, we do not want our course to be unindexed
        # (on modification events, e.g. assessment policies modified) because
        # this validator returns None.
        if isinstance(obj, IndexRecord):
            self.site = unicode(getSite().__name__)
        elif   ICourseInstanceEnrollmentRecord.providedBy(obj) \
            or ICourseInstance.providedBy(obj):
            course = ICourseInstance(obj, None)
            self.site = get_course_site(course) or getSite().__name__

    def __reduce__(self):
        raise TypeError()


class SingleSiteIndex(ValueIndex):
    default_field_name = 'site'
    default_interface = ValidatingSiteName


class UsernameIndex(KeepSetIndex):

    def to_iterable(self, value):
        if isinstance(value, IndexRecord):
            result = (unicode_(value.username),)
        elif ICourseInstanceEnrollmentRecord.providedBy(value):
            principal = value.Principal
            result = (principal.id,) if principal is not None else ()
        else:
            result = ()
        return result


class ScopeSetIndex(KeepSetIndex):

    def to_iterable(self, value):
        if isinstance(value, IndexRecord):
            result = (unicode_(value.Scope),)
        elif ICourseInstanceEnrollmentRecord.providedBy(value):
            result = (unicode_(value.Scope),)
        else:
            result = ()
        return result


class ValidatingCatalogEntryID(object):

    __slots__ = (b'ntiid',)

    def __init__(self, obj, default=None):
        # See site index notes.
        if isinstance(obj, IndexRecord):
            self.ntiid = unicode_(obj.ntiid)
        elif ICourseInstanceEnrollmentRecord.providedBy(obj) \
                or ICourseInstance.providedBy(obj):
            course = getattr(obj, 'CourseInstance', obj)
            entry = ICourseCatalogEntry(course, None)
            if entry is not None:
                self.ntiid = unicode_(entry.ntiid)

    def __reduce__(self):
        raise TypeError()


class CatalogEntryIDIndex(ValueIndex):
    default_field_name = 'ntiid'
    default_interface = ValidatingCatalogEntryID


class RecordCreatedTimeRawIndex(RawIntegerValueIndex):
    pass


def RecordCreatedTimeIndex(family=None):
    return NormalizationWrapper(field_name='createdTime',
                                interface=ICourseInstanceEnrollmentRecord,
                                index=RecordCreatedTimeRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


class RecordLastModifiedRawIndex(RawIntegerValueIndex):
    pass


def RecordLastModifiedIndex(family=None):
    return NormalizationWrapper(field_name='lastModified',
                                interface=ICourseInstanceEnrollmentRecord,
                                index=RecordLastModifiedRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


@interface.implementer(ICatalog)
class EnrollmentCatalog(Catalog):
    pass


def install_enrollment_catalog(site_manager_container, intids=None):
    lsm = site_manager_container.getSiteManager()
    intids = lsm.getUtility(IIntIds) if intids is None else intids
    catalog = lsm.queryUtility(ICatalog, name=ENROLLMENT_CATALOG_NAME)
    if catalog is not None:
        return catalog

    catalog = EnrollmentCatalog(family=intids.family)
    locate(catalog, site_manager_container, ENROLLMENT_CATALOG_NAME)
    intids.register(catalog)
    lsm.registerUtility(catalog,
                        provided=ICatalog,
                        name=ENROLLMENT_CATALOG_NAME)

    for name, clazz in ((IX_SCOPE, ScopeSetIndex),
                        (IX_SITE, SingleSiteIndex),
                        (IX_USERNAME, UsernameIndex),
                        (IX_ENTRY, CatalogEntryIDIndex),
                        (IX_CREATEDTIME, RecordCreatedTimeIndex),
                        (IX_LASTMODIFIED, RecordLastModifiedIndex)):
        index = clazz(family=intids.family)
        intids.register(index)
        locate(index, catalog, name)
        catalog[name] = index
    return catalog


# Courses catalog


IX_NAME = 'name'
IX_PACKAGES = 'packages'
IX_KEYWORDS = 'keywords'
COURSES_CATALOG_NAME = 'nti.dataserver.++etc++courses-catalog'


class ValidatingCourseSiteName(object):

    __slots__ = (b'site',)

    def __init__(self, obj, default=None):
        if ICourseInstance.providedBy(obj):
            self.site = get_course_site(obj) or u''

    def __reduce__(self):
        raise TypeError()


class CourseSiteIndex(ValueIndex):
    default_field_name = 'site'
    default_interface = ValidatingCourseSiteName


class ValidatingCourseName(object):

    __slots__ = (b'name',)

    def __init__(self, obj, default=None):
        if ICourseInstance.providedBy(obj):
            self.name = obj.__name__

    def __reduce__(self):
        raise TypeError()


class CourseNameIndex(ValueIndex):
    default_field_name = 'name'
    default_interface = ValidatingCourseName


class ValidatingCourseCatalogEntry(object):

    __slots__ = (b'ntiid',)

    def __init__(self, obj, default=None):
        if ICourseInstance.providedBy(obj):
            entry = ICourseCatalogEntry(obj, None)
            self.ntiid = getattr(entry, 'ntiid', None)

    def __reduce__(self):
        raise TypeError()


class CourseCatalogEntryIndex(ValueIndex):
    default_field_name = 'ntiid'
    default_interface = ValidatingCourseCatalogEntry


class ValidatingCoursePackages(object):

    __slots__ = (b'packages',)

    def __init__(self, obj, default=None):
        if ICourseInstance.providedBy(obj):
            packs = get_course_packages(obj)
            self.packages = {getattr(x, 'ntiid', None) for x in packs}
            self.packages.discard(None)

    def __reduce__(self):
        raise TypeError()


class CoursePackagesIndex(AttributeSetIndex):
    default_field_name = 'packages'
    default_interface = ValidatingCoursePackages


class CourseKeywordsIndex(AttributeKeywordIndex):
    default_field_name = 'keywords'
    default_interface = ICourseKeywords


@interface.implementer(ICatalog)
class CoursesCatalog(Catalog):
    pass


def install_courses_catalog(site_manager_container, intids=None):
    lsm = site_manager_container.getSiteManager()
    intids = lsm.getUtility(IIntIds) if intids is None else intids
    catalog = lsm.queryUtility(ICatalog, name=COURSES_CATALOG_NAME)
    if catalog is not None:
        return catalog

    catalog = CoursesCatalog(family=intids.family)
    locate(catalog, site_manager_container, COURSES_CATALOG_NAME)
    intids.register(catalog)
    lsm.registerUtility(catalog,
                        provided=ICatalog,
                        name=COURSES_CATALOG_NAME)

    for name, clazz in ((IX_NAME, CourseNameIndex),
                        (IX_SITE, CourseSiteIndex),
                        (IX_PACKAGES, CoursePackagesIndex),
                        (IX_KEYWORDS, CourseKeywordsIndex),
                        (IX_ENTRY, CourseCatalogEntryIndex)):
        index = clazz(family=intids.family)
        intids.register(index)
        locate(index, catalog, name)
        catalog[name] = index
    return catalog


# outline catalog


IX_SOURCE = 'source'
IX_CONTENT_UNIT = 'ContentUnit'
IX_LESSON_OVERVIEW = 'LessonOverview'
IX_AVAILABLE_ENDING = 'AvailableEnding'
IX_AVAILABLE_BEGINNING = 'AvailableBeginning'
COURSE_OUTLINE_CATALOG_NAME = 'nti.dataserver.++etc++course-outline-catalog'


class NodeSrcIndex(ValueIndex):
    default_field_name = 'src'
    default_interface = ICourseOutlineNode


class NodeContentUnitIndex(ValueIndex):
    default_field_name = 'ContentNTIID'
    default_interface = ICourseOutlineNode


class NodeLessonOverviewIndex(ValueIndex):
    default_field_name = 'LessonOverviewNTIID'
    default_interface = ICourseOutlineNode


class ValidatingAvailableBeginning(object):

    __slots__ = (b'AvailableBeginning',)

    def __init__(self, obj, default=None):
        if      ICourseOutlineCalendarNode.providedBy(obj) \
            and obj.AvailableBeginning is not None:
            self.AvailableBeginning = time.mktime(obj.AvailableBeginning.timetuple())

    def __reduce__(self):
        raise TypeError()


class NodeAvailableBeginningRawIndex(RawIntegerValueIndex):
    pass


def NodeAvailableBeginningIndex(family=None):
    return NormalizationWrapper(field_name='AvailableBeginning',
                                interface=ValidatingAvailableBeginning,
                                index=NodeAvailableBeginningRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


class ValidatingAvailableEnding(object):

    __slots__ = (b'AvailableEnding',)

    def __init__(self, obj, default=None):
        if      ICourseOutlineCalendarNode.providedBy(obj) \
            and obj.AvailableEnding is not None:
            self.AvailableEnding = time.mktime(obj.AvailableEnding.timetuple())

    def __reduce__(self):
        raise TypeError()


class NodeAvailableEndingRawIndex(RawIntegerValueIndex):
    pass


def NodeAvailableEndingIndex(family=None):
    return NormalizationWrapper(field_name='AvailableEnding',
                                interface=ValidatingAvailableEnding,
                                index=NodeAvailableEndingRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


@interface.implementer(ICatalog)
class CourseOutlineCatalog(Catalog):
    pass


def install_course_outline_catalog(site_manager_container, intids=None):
    lsm = site_manager_container.getSiteManager()
    intids = lsm.getUtility(IIntIds) if intids is None else intids
    catalog = lsm.queryUtility(ICatalog, name=COURSE_OUTLINE_CATALOG_NAME)
    if catalog is not None:
        return catalog

    catalog = CourseOutlineCatalog(family=intids.family)
    locate(catalog, site_manager_container, COURSE_OUTLINE_CATALOG_NAME)
    intids.register(catalog)
    lsm.registerUtility(catalog,
                        provided=ICatalog,
                        name=COURSE_OUTLINE_CATALOG_NAME)

    for name, clazz in ((IX_SOURCE, NodeSrcIndex),
                        (IX_CONTENT_UNIT, NodeContentUnitIndex),
                        (IX_LESSON_OVERVIEW, NodeLessonOverviewIndex),
                        (IX_AVAILABLE_ENDING, NodeAvailableEndingIndex),
                        (IX_AVAILABLE_BEGINNING, NodeAvailableBeginningIndex)):
        index = clazz(family=intids.family)
        intids.register(index)
        locate(index, catalog, name)
        catalog[name] = index
    return catalog

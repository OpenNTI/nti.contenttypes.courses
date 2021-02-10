#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time

import BTrees

from zope import component
from zope import interface

from zope.catalog.interfaces import ICatalog

from zope.component.hooks import getSite

from zope.deprecation import deprecated

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.base._compat import text_

from nti.contenttypes.courses.common import get_course_site
from nti.contenttypes.courses.common import get_course_packages
from nti.contenttypes.courses.common import get_course_editors
from nti.contenttypes.courses.common import get_course_instructors

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseKeywords
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseImportMetadata
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

logger = __import__('logging').getLogger(__name__)


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


class IndexRecord(object):

    __slots__ = ('username', 'ntiid', 'Scope', 'site')

    def __init__(self, username=None, ntiid=None, scope=None, site=None):
        self.site = site
        self.ntiid = ntiid
        self.Scope = scope
        self.username = username

    @property
    def scope(self):
        return self.Scope


ENROLLMENT_CATALOG_NAME = 'nti.dataserver.++etc++enrollment-catalog'

IX_SITE = 'site'
IX_SCOPE = 'scope'
IX_CREATEDTIME = 'createdTime'
IX_ENTRY = IX_COURSE = 'course'
IX_LASTMODIFIED = 'lastModified'
IX_USERNAME = IX_STUDENT = IX_INSTRUCTOR = 'username'


class ValidatingSiteName(object):

    __slots__ = ('site',)

    def __init__(self, obj, unused_default=None):
        # For value indexes, we do not want our course to be unindexed
        # (on modification events, e.g. assessment policies modified) because
        # this validator returns None.
        current_site = getattr(getSite(), '__name__', None)
        if isinstance(obj, IndexRecord):
            self.site = obj.site or current_site
            self.site = text_(self.site)
        elif   ICourseInstanceEnrollmentRecord.providedBy(obj) \
            or ICourseInstance.providedBy(obj):
            course = ICourseInstance(obj, None)
            self.site = get_course_site(course) or current_site

    def __reduce__(self):
        raise TypeError()


class SingleSiteIndex(ValueIndex):
    default_field_name = 'site'
    default_interface = ValidatingSiteName


class UsernameIndex(KeepSetIndex):

    def to_iterable(self, value):
        if isinstance(value, IndexRecord):
            result = (text_(value.username),)
        elif ICourseInstanceEnrollmentRecord.providedBy(value):
            principal = value.Principal
            result = (principal.id,) if principal is not None else ()
        else:
            result = ()
        return result


class ScopeSetIndex(KeepSetIndex):

    def to_iterable(self, value):
        if isinstance(value, IndexRecord):
            result = (text_(value.Scope),)
        elif ICourseInstanceEnrollmentRecord.providedBy(value):
            result = (text_(value.Scope),)
        else:
            result = ()
        return result


class ValidatingCatalogEntryID(object):

    __slots__ = ('ntiid',)

    def __init__(self, obj, unused_default=None):
        # See site index notes.
        # Because IndexRecord points to a course int id
        # we want always to index the course
        if isinstance(obj, IndexRecord):
            self.ntiid = text_(obj.ntiid)
        elif   ICourseInstanceEnrollmentRecord.providedBy(obj) \
            or ICourseInstance.providedBy(obj):
            course = getattr(obj, 'CourseInstance', obj)
            course = ICourseInstance(obj, None)
            entry = ICourseCatalogEntry(course, None)
            if entry is not None:
                self.ntiid = text_(entry.ntiid)

    def __reduce__(self):
        raise TypeError()


class CatalogEntryIDIndex(ValueIndex):
    default_field_name = 'ntiid'
    default_interface = ValidatingCatalogEntryID


class RecordCreatedTimeRawIndex(RawIntegerValueIndex):
    pass


def RecordCreatedTimeIndex(family=BTrees.family64):
    return NormalizationWrapper(field_name='createdTime',
                                interface=ICourseInstanceEnrollmentRecord,
                                index=RecordCreatedTimeRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


class RecordLastModifiedRawIndex(RawIntegerValueIndex):
    pass


def RecordLastModifiedIndex(family=BTrees.family64):
    return NormalizationWrapper(field_name='lastModified',
                                interface=ICourseInstanceEnrollmentRecord,
                                index=RecordLastModifiedRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


@interface.implementer(ICatalog)
class EnrollmentCatalog(Catalog):
    pass


def get_enrollment_catalog(registry=component):
    return registry.queryUtility(ICatalog, name=ENROLLMENT_CATALOG_NAME)


def create_enrollment_catalog(catalog=None, family=BTrees.family64):
    if catalog is None:
        catalog = EnrollmentCatalog(family=family)
    for name, clazz in ((IX_SCOPE, ScopeSetIndex),
                        (IX_SITE, SingleSiteIndex),
                        (IX_USERNAME, UsernameIndex),
                        (IX_ENTRY, CatalogEntryIDIndex),
                        (IX_CREATEDTIME, RecordCreatedTimeIndex),
                        (IX_LASTMODIFIED, RecordLastModifiedIndex)):
        index = clazz(family=family)
        locate(index, catalog, name)
        catalog[name] = index
    return catalog


def install_enrollment_catalog(site_manager_container, intids=None):
    lsm = site_manager_container.getSiteManager()
    catalog = get_enrollment_catalog(lsm)
    if catalog is not None:
        return catalog

    intids = lsm.getUtility(IIntIds) if intids is None else intids
    catalog = create_enrollment_catalog(family=intids.family)
    locate(catalog, site_manager_container, ENROLLMENT_CATALOG_NAME)
    intids.register(catalog)
    lsm.registerUtility(catalog,
                        provided=ICatalog,
                        name=ENROLLMENT_CATALOG_NAME)

    for index in catalog.values():
        intids.register(index)
    return catalog


# Courses catalog

#: Important to only allow course instances in the indexes
#: for course attributes (instructors, editors) and only
#: allow catalog entries in for the entry-specific indexes.
#: Otherwise, we run the risk of having a course indexed to a
#: set of attributes and its entry indexed to another set of
#: attributes.
IX_NAME = 'name'
IX_TAGS = 'tags'
IX_KEYWORDS = 'keywords'
IX_PACKAGES = 'packages'
IX_IMPORT_HASH = 'import_hash'
IX_COURSE_INSTRUCTOR = 'instructor'
IX_COURSE_EDITOR = 'editor'
IX_ENTRY_TITLE = 'title'
IX_ENTRY_DESC = 'description'
IX_ENTRY_PUID = 'provider_unique_id'
IX_ENTRY_START_DATE = 'StartDate'
IX_ENTRY_END_DATE = 'EndDate'
COURSES_CATALOG_NAME = 'nti.dataserver.++etc++courses-catalog'


class InstructorSetIndex(RawSetIndex):

    def to_iterable(self, value):
        result = []
        if ICourseInstance.providedBy(value):
            for x in get_course_instructors(value) or ():
                principal_id = getattr(x, 'id', x)
                if principal_id is not None:
                    result.append(principal_id)
        return result

    def index_doc(self, doc_id, value):
        value = self.to_iterable(value)
        super(InstructorSetIndex, self).index_doc(doc_id, value)


class EditorSetIndex(RawSetIndex):

    def to_iterable(self, value):
        result = []
        if ICourseInstance.providedBy(value):
            for x in get_course_editors(value) or ():
                principal_id = getattr(x, 'id', x)
                if principal_id is not None:
                    result.append(principal_id)
        return result

    def index_doc(self, doc_id, value):
        value = self.to_iterable(value)
        super(EditorSetIndex, self).index_doc(doc_id, value)


class ValidatingCourseSiteName(object):

    __slots__ = ('site',)

    def __init__(self, obj, unused_default=None):
        if     ICourseInstance.providedBy(obj) \
            or ICourseCatalogEntry.providedBy(obj):
            self.site = text_(get_course_site(obj) or '')

    def __reduce__(self):
        raise TypeError()


class CourseSiteIndex(ValueIndex):
    default_field_name = 'site'
    default_interface = ValidatingCourseSiteName


class CourseImportHashIndex(ValueIndex):
    default_field_name = 'import_hash'
    default_interface = ICourseImportMetadata


class ValidatingCourseName(object):

    __slots__ = ('name',)

    def __init__(self, obj, unused_default=None):
        if ICourseInstance.providedBy(obj):
            self.name = obj.__name__

    def __reduce__(self):
        raise TypeError()


class CourseNameIndex(ValueIndex):
    default_field_name = 'name'
    default_interface = ValidatingCourseName


class ValidatingCourseCatalogEntry(object):

    __slots__ = ('ntiid',)

    def __init__(self, obj, unused_default=None):
        if ICourseInstance.providedBy(obj):
            entry = ICourseCatalogEntry(obj, None)
            self.ntiid = getattr(entry, 'ntiid', None)

    def __reduce__(self):
        raise TypeError()


class CourseCatalogEntryIndex(ValueIndex):
    default_field_name = 'ntiid'
    default_interface = ValidatingCourseCatalogEntry


class ValidatingCourseCatalogEntryTitle(object):

    __slots__ = ('title',)

    def __init__(self, obj, unused_default=None):
        if ICourseCatalogEntry.providedBy(obj):
            self.title = getattr(obj, 'title', None)

    def __reduce__(self):
        raise TypeError()


class CourseCatalogEntryTitleIndex(ValueIndex):
    default_field_name = 'title'
    default_interface = ValidatingCourseCatalogEntryTitle


class ValidatingCourseCatalogEntryDescription(object):

    __slots__ = ('description',)

    def __init__(self, obj, unused_default=None):
        if ICourseCatalogEntry.providedBy(obj):
            self.description = getattr(obj, 'description', None)

    def __reduce__(self):
        raise TypeError()


class CourseCatalogEntryDescriptionIndex(ValueIndex):
    default_field_name = 'description'
    default_interface = ValidatingCourseCatalogEntryDescription


class ValidatingCourseCatalogEntryPUID(object):

    __slots__ = ('ProviderUniqueID',)

    def __init__(self, obj, unused_default=None):
        if ICourseCatalogEntry.providedBy(obj):
            self.ProviderUniqueID = getattr(obj, 'ProviderUniqueID', None)

    def __reduce__(self):
        raise TypeError()


class CourseCatalogEntryPUIDIndex(ValueIndex):
    default_field_name = 'ProviderUniqueID'
    default_interface = ValidatingCourseCatalogEntryPUID


class StartDateAdapter(object):

    __slots__ = (b'StartDate',)

    def __init__(self, obj, default=None):
        if not ICourseCatalogEntry.providedBy(obj):
            return
        if obj.StartDate is not None:
            self.StartDate = obj.StartDate

    def __reduce__(self):
        raise TypeError()


class EndDateAdapter(object):

    __slots__ = (b'EndDate',)

    def __init__(self, obj, default=None):
        if not ICourseCatalogEntry.providedBy(obj):
            return
        if obj.EndDate is not None:
            self.EndDate = obj.EndDate

    def __reduce__(self):
        raise TypeError()


def CourseCatalogEntryStartDateIndex(family=BTrees.family64):
    return NormalizationWrapper(field_name=IX_ENTRY_START_DATE,
                                interface=StartDateAdapter,
                                index=RawIntegerValueIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


def CourseCatalogEntryEndDateIndex(family=BTrees.family64):
    return NormalizationWrapper(field_name=IX_ENTRY_END_DATE,
                                interface=EndDateAdapter,
                                index=RawIntegerValueIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


class ValidatingCoursePackages(object):

    __slots__ = ('packages',)

    def __init__(self, obj, unused_default=None):
        if ICourseInstance.providedBy(obj):
            packs = get_course_packages(obj)
            self.packages = {
                getattr(x, 'ntiid', None) for x in packs
            }
            self.packages.discard(None)

    def __reduce__(self):
        raise TypeError()


class CoursePackagesIndex(AttributeSetIndex):  # pylint: disable=inconsistent-mro
    default_field_name = 'packages'
    default_interface = ValidatingCoursePackages


class ValidatingCourseTags(object):

    __slots__ = ('tags',)

    def __init__(self, obj, unused_default=None):
        if ICourseCatalogEntry.providedBy(obj):
            self.tags = getattr(obj, 'tags', None)

    def __reduce__(self):
        raise TypeError()


class CourseTagsIndex(AttributeKeywordIndex):
    default_field_name = 'tags'
    default_interface = ValidatingCourseTags


class CourseKeywordsIndex(AttributeKeywordIndex):
    default_field_name = 'keywords'
    default_interface = ICourseKeywords


@interface.implementer(ICatalog)
class CoursesCatalog(Catalog):
    pass


def get_courses_catalog(registry=component):
    return registry.queryUtility(ICatalog, name=COURSES_CATALOG_NAME)


def create_courses_catalog(catalog=None, family=BTrees.family64):
    if catalog is None:
        catalog = CoursesCatalog(family=family)
    for name, clazz in ((IX_NAME, CourseNameIndex),
                        (IX_SITE, CourseSiteIndex),
                        (IX_TAGS, CourseTagsIndex),
                        (IX_PACKAGES, CoursePackagesIndex),
                        (IX_KEYWORDS, CourseKeywordsIndex),
                        (IX_ENTRY, CourseCatalogEntryIndex),
                        (IX_ENTRY_TITLE, CourseCatalogEntryTitleIndex),
                        (IX_ENTRY_DESC, CourseCatalogEntryDescriptionIndex),
                        (IX_ENTRY_PUID, CourseCatalogEntryPUIDIndex),
                        (IX_ENTRY_START_DATE, CourseCatalogEntryStartDateIndex),
                        (IX_ENTRY_END_DATE, CourseCatalogEntryEndDateIndex),
                        (IX_IMPORT_HASH, CourseImportHashIndex),
                        (IX_COURSE_INSTRUCTOR, InstructorSetIndex),
                        (IX_COURSE_EDITOR, EditorSetIndex)):
        index = clazz(family=family)
        locate(index, catalog, name)
        catalog[name] = index
    return catalog


def install_courses_catalog(site_manager_container, intids=None):
    lsm = site_manager_container.getSiteManager()
    catalog = get_courses_catalog(lsm)
    if catalog is not None:
        return catalog

    intids = lsm.getUtility(IIntIds) if intids is None else intids
    catalog = create_courses_catalog(family=intids.family)
    locate(catalog, site_manager_container, COURSES_CATALOG_NAME)
    intids.register(catalog)
    lsm.registerUtility(catalog,
                        provided=ICatalog,
                        name=COURSES_CATALOG_NAME)

    for index in catalog.values():
        intids.register(index)
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

    __slots__ = ('AvailableBeginning',)

    def __init__(self, obj, unused_default=None):
        if      ICourseOutlineCalendarNode.providedBy(obj) \
            and obj.AvailableBeginning is not None:
            data = obj.AvailableBeginning.timetuple()
            self.AvailableBeginning = time.mktime(data)

    def __reduce__(self):
        raise TypeError()


class NodeAvailableBeginningRawIndex(RawIntegerValueIndex):
    pass


def NodeAvailableBeginningIndex(family=BTrees.family64):
    return NormalizationWrapper(field_name='AvailableBeginning',
                                interface=ValidatingAvailableBeginning,
                                index=NodeAvailableBeginningRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


class ValidatingAvailableEnding(object):

    __slots__ = ('AvailableEnding',)

    def __init__(self, obj, unused_default=None):
        if      ICourseOutlineCalendarNode.providedBy(obj) \
            and obj.AvailableEnding is not None:
            data = obj.AvailableEnding.timetuple()
            self.AvailableEnding = time.mktime(data)

    def __reduce__(self):
        raise TypeError()


class NodeAvailableEndingRawIndex(RawIntegerValueIndex):
    pass


def NodeAvailableEndingIndex(family=BTrees.family64):
    return NormalizationWrapper(field_name='AvailableEnding',
                                interface=ValidatingAvailableEnding,
                                index=NodeAvailableEndingRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


@interface.implementer(ICatalog)
class CourseOutlineCatalog(Catalog):
    pass


def get_course_outline_catalog(registry=component):
    return registry.queryUtility(ICatalog, name=COURSE_OUTLINE_CATALOG_NAME)


def create_course_outline_catalog(catalog=None, family=BTrees.family64):
    if catalog is None:
        catalog = CourseOutlineCatalog(family=family)
    for name, clazz in ((IX_SOURCE, NodeSrcIndex),
                        (IX_CONTENT_UNIT, NodeContentUnitIndex),
                        (IX_LESSON_OVERVIEW, NodeLessonOverviewIndex),
                        (IX_AVAILABLE_ENDING, NodeAvailableEndingIndex),
                        (IX_AVAILABLE_BEGINNING, NodeAvailableBeginningIndex)):
        index = clazz(family=family)
        locate(index, catalog, name)
        catalog[name] = index
    return catalog


def install_course_outline_catalog(site_manager_container, intids=None):
    lsm = site_manager_container.getSiteManager()
    catalog = get_course_outline_catalog(lsm)
    if catalog is not None:
        return catalog

    intids = lsm.getUtility(IIntIds) if intids is None else intids
    catalog = create_course_outline_catalog(family=intids.family)
    locate(catalog, site_manager_container, COURSE_OUTLINE_CATALOG_NAME)
    intids.register(catalog)
    lsm.registerUtility(catalog,
                        provided=ICatalog,
                        name=COURSE_OUTLINE_CATALOG_NAME)

    for index in catalog.values():
        intids.register(index)
    return catalog

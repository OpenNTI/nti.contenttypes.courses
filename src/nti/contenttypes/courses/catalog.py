#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementations of course catalogs.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from datetime import datetime
from functools import total_ordering

from zope import component
from zope import interface

from zope.annotation.interfaces import IAttributeAnnotatable

from zope.cachedescriptors.property import readproperty
from zope.cachedescriptors.property import CachedProperty

from zope.intid.interfaces import IIntIds

from nti.containers.containers import CheckingLastModifiedBTreeFolder
from nti.containers.containers import CheckingLastModifiedBTreeContainer

from nti.contentlibrary.presentationresource import DisplayableContentMixin

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_ENTRY

from nti.contenttypes.courses.index import get_courses_catalog

from nti.contenttypes.courses.interfaces import ICatalogFamily
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IGlobalCourseCatalog
from nti.contenttypes.courses.interfaces import IPersistentCourseCatalog
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import ICourseCatalogInstructorInfo

from nti.contenttypes.courses.utils import path_for_entry

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.interfaces import IHostPolicyFolder

from nti.dublincore.time_mixins import CreatedAndModifiedTimeMixin

from nti.externalization.persistence import NoPickle
from nti.externalization.representation import WithRepr

from nti.links.links import Link

from nti.property.property import alias
from nti.property.property import LazyOnClass

from nti.recorder.mixins import RecordableMixin

from nti.schema.eqhash import EqHash

from nti.schema.fieldproperty import AdaptingFieldProperty
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import PermissiveSchemaConfigured as SchemaConfigured

from nti.site.localutility import queryNextUtility

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


def _queryNextCatalog(context):
    return queryNextUtility(context, ICourseCatalog)


class _AbstractCourseCatalogMixin(object):
    """
    Defines the interface methods for a generic course
    catalog, including tree searching.
    """

    __name__ = u'CourseCatalog'
    mime_type = mimeType = 'application/vnd.nextthought.courses.coursecatalogfolder'

    anonymously_accessible = False

    @LazyOnClass
    def __acl__(self):
        # Got to be here after the components are registered
        # Everyone logged in has read and search access to the catalog
        return acl_from_aces(ace_allowing(AUTHENTICATED_GROUP_NAME,
                                          ACT_READ,
                                          type(self)))

    # regardless of length, catalogs are True
    def __bool__(self):
        return True
    __nonzero__ = __bool__

    @property
    def _next_catalog(self):
        return _queryNextCatalog(self)

    def isEmpty(self):
        raise NotImplementedError()

    def _iter_entries(self):
        """
        Iterate over course catalog entries.
        """
        raise NotImplementedError()

    def iterCatalogEntries(self):
        seen = set()
        for entry in self._iter_entries():
            if entry.ntiid is None or entry.ntiid in seen:
                continue
            seen.add(entry.ntiid)
            yield entry

        parent = self._next_catalog
        if parent is not None:
            for e in parent.iterCatalogEntries():
                if e.ntiid not in seen:
                    seen.add(e.ntiid)
                    yield e

    def _primary_query_my_entry(self, name):
        raise NotImplementedError()

    def _query_my_entry(self, name):
        entry = self._primary_query_my_entry(name)
        return entry

    def getCatalogEntry(self, name):
        entry = self._query_my_entry(name)
        if entry is not None:
            return entry

        parent = self._next_catalog
        if parent is None:
            raise KeyError(name)
        return parent.getCatalogEntry(name)

    def get_admin_levels(self, parents=True):
        # XXX: Check recursively?
        result = dict()
        for key, val in self.items():
            if ICourseAdministrativeLevel.providedBy(val):
                result[key] = val
        if parents:
            parent = self._next_catalog
            if parent is not None:
                for key, val in parent.get_admin_levels().items():
                    if key not in result:
                        result[key] = val
        return result
    getAdminLevels = get_admin_levels


@NoPickle
@WithRepr
@interface.implementer(IGlobalCourseCatalog)
class GlobalCourseCatalog(_AbstractCourseCatalogMixin,
                          CheckingLastModifiedBTreeContainer):

    # NOTE: We happen to inherit Persistent, which we really
    # don't want.

    lastModified = 0

    def _iter_entries(self):
        return self.values()

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
            raise ValueError("The entry has no NTIID or name", entry)
        if CheckingLastModifiedBTreeContainer.__contains__(self, key):
            if entry.__parent__ is self:
                return
            raise ValueError("Adding duplicate entry", entry)

        if event:
            self[key] = entry
        else:
            self._setitemf(key, entry)
            entry.__parent__ = self

        self.lastModified = max(self.lastModified, entry.lastModified)

    append = addCatalogEntry

    def removeCatalogEntry(self, entry, event=True):
        """
        Remove an entry from this catalog.

        :keyword bool event: If true (the default), we broadcast
                the object removed event.
        """
        key = entry.ntiid or entry.__name__
        if not key:
            raise ValueError("The entry has no NTIID or name", entry)

        __traceback_info__ = key, entry  # pylint: disable=unused-variable
        if not event:
            l = self._BTreeContainer__len
            try:
                entry = self._SampleContainer__data[key]
                del self._SampleContainer__data[key]
                # pylint: disable=no-member
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


@WithRepr
@interface.implementer(ICourseCatalogInstructorInfo)
class CourseCatalogInstructorInfo(SchemaConfigured):
    createDirectFieldProperties(ICourseCatalogInstructorInfo)


@WithRepr
@interface.implementer(ICatalogFamily)
class CatalogFamily(SchemaConfigured,
                    DisplayableContentMixin):
    # shut up pylint
    title = None
    EndDate = None
    StartDate = None
    DisplayName = None
    description = None
    ProviderUniqueID = None

    createDirectFieldProperties(ICatalogFamily)

    # legacy compatibility
    Title = alias('title')
    Description = alias('description')

    def __init__(self, *args, **kwargs):
        SchemaConfigured.__init__(self, *args, **kwargs)  # not cooperative


@total_ordering
@EqHash('ntiid')
@interface.implementer(ICourseCatalogEntry, IAttributeAnnotatable)
class CourseCatalogEntry(CatalogFamily,
                         CreatedAndModifiedTimeMixin,
                         RecordableMixin):
    createDirectFieldProperties(ICourseCatalogEntry)

    _SET_CREATED_MODTIME_ON_INIT = False

    # shut up pylint
    ntiid = None
    Duration = None
    lastSynchronized = 0
    awardable_credits = ()

    RichDescription = AdaptingFieldProperty(ICourseCatalogEntry['RichDescription'])

    __name__ = alias('ntiid')
    __parent__ = None

    def __init__(self, *args, **kwargs):  # pylint: disable=super-init-not-called
        CatalogFamily.__init__(self, *args, **kwargs)
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
        result = ()
        instance = ICourseInstance(self, None)
        if instance is not None:
            result = [Link(instance, rel="CourseInstance")]
        return result

    @property
    def PlatformPresentationResources(self):
        """
        If we do not have a set of presentation assets,
        we echo the first thing we have that does contain
        them. This should simplify things for the clients.
        """
        ours = super(CourseCatalogEntry, self).PlatformPresentationResources
        if ours: # pylint: disable=using-constant-test
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

        # Does it have resources?
        try:
            theirs = course.PlatformPresentationResources
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
    def AdditionalProperties(self):
        return None

    @readproperty
    def InstructorsSignature(self):
        sig_lines = []
        # pylint: disable=no-member
        for inst in self.Instructors or ():
            sig_lines.append(inst.Name)
            if inst.JobTitle:
                sig_lines.append(inst.JobTitle)
            sig_lines.append("")
        if sig_lines:
            # always at least one instructor. take off the last trailing line
            del sig_lines[-1]
        signature = u'\n\n'.join(sig_lines)
        return signature

    def isCourseCurrentlyActive(self):
        # XXX: duplicated for legacy sub-catalog entries
        if getattr(self, 'Preview', False):
            # either manually set, or before the start date
            # some objects don't have this flag at all
            return False
        if self.EndDate:
            # if we end in the future we're active
            return self.EndDate > datetime.utcnow()
        # otherwise, with no information given, assume
        # we're active
        return True

    @CachedProperty('__parent__')
    def relative_path(self):
        return path_for_entry(self)
    
    def _get_seat_limit(self):
        if 'seat_limit' in self.__dict__:
            return self.__dict__['seat_limit']

    def _set_seat_limit(self, seat_limit):
        if seat_limit is not None:
            seat_limit.__parent__ = self
        self.__dict__['seat_limit'] = seat_limit

    def _del_seat_limit(self):
        if 'seat_limit' in self.__dict__:
            del self.__dict__['seat_limit']

    seat_limit = property(_get_seat_limit, _set_seat_limit, _del_seat_limit)
    

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

    def isEmpty(self):
        return not bool(self._course_intid_iter())

    @property
    def _catalog_site(self):
        catalog_site = find_interface(self, IHostPolicyFolder, strict=False)
        return catalog_site

    def _get_entry_from_course_intid(self, course_intid):
        intids = component.getUtility(IIntIds)
        course = intids.queryObject(course_intid)
        return ICourseCatalogEntry(course, None)

    def _course_intid_iter(self):
        """
        Iterate over course intids.
        """
        catalog = get_courses_catalog()
        current_site = getattr(self._catalog_site, '__name__', None)
        result = ()
        if current_site:
            query = {IX_SITE: {'any_of': (current_site,)}}
            result = catalog.apply(query)
        return result

    def _iter_entries(self):
        """
        Iterate over course catalog entries.
        """
        for course_intid in self._course_intid_iter():
            entry = self._get_entry_from_course_intid(course_intid)
            if entry is not None:
                yield entry

    def _primary_query_my_entry(self, name):
        catalog = get_courses_catalog()
        query = {IX_ENTRY: {'any_of': (name,)}}
        current_site = getattr(self._catalog_site, '__name__', None)
        if current_site:
            query[IX_SITE] = {'any_of': (current_site,)}
        rs = catalog.apply(query)
        if rs:
            return self._get_entry_from_course_intid(rs[0])

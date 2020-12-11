#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementations of enrollment related structures and utilities.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import sys
import random
from collections import Mapping
from functools import total_ordering

import BTrees

from persistent import Persistent

import six

from zc.intid.interfaces import IBeforeIdRemovedEvent

from ZODB.interfaces import IConnection

from zope import component
from zope import interface

from zope.annotation.factory import factory as an_factory

from zope.cachedescriptors.method import cachedIn

from zope.cachedescriptors.property import Lazy
from zope.cachedescriptors.property import CachedProperty

from zope.container.interfaces import IContained

from zope.event import notify

from zope.interface import ro

from zope.keyreference.interfaces import NotYet
from zope.keyreference.interfaces import IKeyReference

from zope.mimetype.interfaces import IContentTypeAware

from zope.security.interfaces import IPrincipal
from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.contentlibrary.bundle import _readCurrent

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IGlobalCourseCatalog
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import InstructorEnrolledException
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord
from nti.contenttypes.courses.interfaces import IDefaultCourseCatalogEnrollmentStorage
from nti.contenttypes.courses.interfaces import IDefaultCourseInstanceEnrollmentStorage
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecordContainer

from nti.contenttypes.courses.utils import is_instructor_in_hierarchy

from nti.dataserver.users.users import User

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.externalization.persistence import NoPickle

from nti.externalization.representation import WithRepr

from nti.property.property import alias

from nti.schema.eqhash import EqHash

from nti.schema.fieldproperty import FieldProperty

from nti.schema.schema import SchemaConfigured

from nti.wref.interfaces import IWeakRef

logger = __import__('logging').getLogger(__name__)

# BWC definition
ICourseInstanceEnrollmentRecordContainer = ICourseInstanceEnrollmentRecordContainer


# Recall that everything that's keyed by username/principalid must be
# case-insensitive


@component.adapter(ICourseInstance)
@interface.implementer(IDefaultCourseInstanceEnrollmentStorage)
class DefaultCourseInstanceEnrollmentStorage(CaseInsensitiveCheckingLastModifiedBTreeContainer):
    pass


_DefaultCourseInstanceEnrollmentStorageFactory = an_factory(DefaultCourseInstanceEnrollmentStorage,
                                                            u'CourseInstanceEnrollmentStorage')


@component.adapter(ICourseInstance)
@interface.implementer(IDefaultCourseInstanceEnrollmentStorage)
def DefaultCourseInstanceEnrollmentStorageFactory(course):
    # pylint: disable=protected-access,too-many-function-args
    result = _DefaultCourseInstanceEnrollmentStorageFactory(course)
    if result._p_jar is None:
        # Despite the write-time code below that attempts to determine
        # a certain connection for this object, we sometimes still get
        # invalid obj ref; it's not clear where we're still reachable from
        # (the intid catalog?)
        try:
            IConnection(course).add(result)
        except (TypeError, AttributeError):
            pass
    return result


@interface.implementer(IContained)
class CourseEnrollmentList(Persistent):
    """
    A set-like object that contains :class:`ICourseInstanceEnrollmentRecord`
    objects.

    Internally, for conflict resolution and efficiency, this is implemented
    as holding IKeyRefererence objects (not weak references---we are a valid
    path to the record). Iterating over this object resolves these references.

    This object should never be directly referenced outside of this module.
    """

    __name__ = None
    __parent__ = None

    def __init__(self):
        self._set_data = BTrees.OOBTree.TreeSet()

    @Lazy
    def _set_data(self):  # pylint: disable=method-hidden
        # We used to be a subclass of PersistentList, which
        # stores its contents in a value called `data`, which is-a
        # list object directly holding references to the CourseEnrollmentRecord
        data_list = self.data  # AttributeError if somehow this migration already happened
        del self.data
        # We migrate these at runtime right now because there are likely to be
        # few of them, and they are likely to be written in many of the scenarios
        # that they are read
        data = BTrees.OOBTree.TreeSet(IKeyReference(x) for x in data_list)
        # pylint: disable=attribute-defined-outside-init
        self._p_changed = True
        return data

    def __iter__(self):
        return (x() for x in self._set_data)

    def __contains__(self, record):
        return IKeyReference(record) in self._set_data

    def add(self, record):
        ref = None
        try:
            ref = IKeyReference(record)
        except NotYet:
            # The record MUST be in a connection at this time
            # so we can get an IKeyReference to it
            # pylint: disable=too-many-function-args
            IConnection(self).add(record)  # may raise TypeError/AttributeError
            ref = IKeyReference(record)
        return self._set_data.add(ref)

    def remove(self, record):
        """
        Remove the record if it exists, raise KeyError if not.
        """
        self._set_data.remove(IKeyReference(record))


@component.adapter(ICourseCatalog)
@interface.implementer(IDefaultCourseCatalogEnrollmentStorage)
class DefaultCourseCatalogEnrollmentStorage(CaseInsensitiveCheckingLastModifiedBTreeContainer):

    __name__ = None
    __parent__ = None

    def enrollments_for_id(self, principalid, principal):
        try:
            return self[principalid]
        except KeyError:
            result = CourseEnrollmentList()
            self[principalid] = result
            return result


DefaultCourseCatalogEnrollmentStorageFactory = an_factory(DefaultCourseCatalogEnrollmentStorage,
                                                          'CourseCatalogEnrollmentStorage')


class GlobalCourseCatalogEnrollmentStorage(DefaultCourseCatalogEnrollmentStorage):
    pass


@component.adapter(IGlobalCourseCatalog)
@interface.implementer(IDefaultCourseCatalogEnrollmentStorage)
def global_course_catalog_enrollment_storage(unused_catalog):
    """
    Global course catalogs are not persisted in the database,
    so we have to find somewhere else to put them.

    When we are called, our current site should be a persistent
    site in the database, so we store things there.
    """

    site_manager = component.getSiteManager()
    try:
        return site_manager['default']['GlobalCourseCatalogEnrollmentStorage']
    except KeyError:
        storage = GlobalCourseCatalogEnrollmentStorage()
        site_manager['default']['GlobalCourseCatalogEnrollmentStorage'] = storage
        # This could be reachable from a few different databases
        # (because records which are children live with their
        # principal's database), so give it a home
        jar = IConnection(storage, None)
        if jar is not None:
            # pylint: disable=too-many-function-args
            jar.add(storage)
        return storage


def _global_course_catalog_storage(site_manager):
    """
    Returns a storage if it exists in the given site manager, otherwise
    returns nothing.
    """
    try:
        return site_manager['default']['GlobalCourseCatalogEnrollmentStorage']
    except (KeyError, TypeError):
        return None


from nti.contenttypes.courses.interfaces import CourseInstanceEnrollmentRecordCreatedEvent


@component.adapter(ICourseInstance)
@interface.implementer(ICourseEnrollmentManager)
class DefaultCourseEnrollmentManager(object):
    """
    The default enrollment manager.

    To be able to efficiently answer questions both starting
    from the course and starting from the principal, we
    store enrollment records directly as an annotation on the course,
    and use the enclosing course catalog entry to store
    a map describing which principals *might* have entries
    in which courses.
    """

    def __init__(self, context, request=None):
        self.context = context
        self.request = request

    _course = alias('context')

    # Use of readCurrent:
    #
    # Although we are modifying a set of related data structures,
    # based off the reading of one of them, we are always doing so in
    # a specific order starting with one particular datastructure;
    # moreover, we are always actually modifying all of them if we
    # modify any of them.
    #
    # Therefore, so long as we readCurrent on the *first* datastructure,
    # we shouldn't need to readCurrent any anything else (because we will
    # actually be making modifications to the remaining objects).
    #
    # The first datastructure is always the _inst_enrollment_storage
    # object.

    @Lazy
    def _inst_enrollment_storage_rc(self):
        storage = self._inst_enrollment_storage
        return _readCurrent(storage)

    @Lazy
    def _inst_enrollment_storage(self):
        return IDefaultCourseInstanceEnrollmentStorage(self._course)

    @Lazy
    def _catalog(self):
        try:
            return component.getUtility(ICourseCatalog, context=self._course)
        except LookupError:
            # Course must be unanchored and/or in the global site?
            # we only expect this is in tests (legacy cases use their
            # own manager)
            return component.getUtility(ICourseCatalog)

    @Lazy
    def _cat_enrollment_storage(self):
        return IDefaultCourseCatalogEnrollmentStorage(self._catalog)

    # NOTE: The enroll/drop methods DO NOT set up any of the scope/sharing
    # information; that's left to ObjectEvent subscribers. That may
    # seem like action at a distance, but the rationale is that we
    # want to, in addition to the Added and Removed events fired here,
    # support Modified events (e.g., a user starts out open/public
    # enrolled, then pays for the course, and becomes for-credit-non-degree)

    def _enrollments_for_id(self, principal_id, principal):
        storage = self._cat_enrollment_storage
        # pylint: disable=no-member
        return storage.enrollments_for_id(principal_id, principal)

    def _new_enrollment_record(self, principal, scope):
        return DefaultCourseInstanceEnrollmentRecord(Principal=principal, Scope=scope)

    def enroll(self, principal, scope=ES_PUBLIC, context=None):
        principal_id = IPrincipal(principal).id
        # pylint: disable=unsupported-membership-test
        if principal_id in self._inst_enrollment_storage:
            # DO NOT readCurrent of this, until we determine that we won't actually
            # change it; if we are going to change it, then the normal conflict
            # error comes into play. only if we do not change it then do we need
            # to assert that we read the current value (and aren't concurrently)
            # dropping---but dropping must always readCurrent
            _readCurrent(self._inst_enrollment_storage)
            return False

        user = User.get_user(principal_id)
        if is_instructor_in_hierarchy(self.context, user):
            entry_ntiid = ICourseCatalogEntry(self.context).ntiid
            logger.warning('Cannot enroll instructor in course (%s) (%s)',
                           principal_id, entry_ntiid)
            raise InstructorEnrolledException()

        record = self._new_enrollment_record(principal, scope)
        notify(CourseInstanceEnrollmentRecordCreatedEvent(record, context))

        enrollments = self._enrollments_for_id(principal_id, principal)
        enrollments.add(record)
        # now install and fire the ObjectAdded event, after
        # it's in the IPrincipalEnrollments; that way
        # event listeners will see consistent data.
        self._inst_enrollment_storage[principal_id] = record
        return record

    def _drop_record_for_principal_id(self, record, principal_id):
        # pylint: disable=no-member
        enrollments = self._cat_enrollment_storage.get(principal_id, ())
        if record in enrollments:
            enrollments.remove(record)
        else:
            # Snap, the enrollment is missing from the course catalog storage of the
            # principal, but we have it in the course instance storage.
            # This is probably that migration problem, so look up the tree to see
            # if we can find the record.
            # Unittests for this code path
            for site_manager in ro.ro(component.getSiteManager()):
                storage = _global_course_catalog_storage(site_manager)
                if storage is not None and principal_id in storage:
                    # we do readCurrent of this because we're walking up an
                    # unrelated tree
                    _readCurrent(storage)
                    enrollments = _readCurrent(storage.get(principal_id, ()))
                    if record in enrollments:
                        enrollments.remove(record)
                        break

    def drop(self, principal):
        # pylint: disable=unsupported-membership-test,unsubscriptable-object
        principal_id = IPrincipal(principal).id
        if principal_id not in self._inst_enrollment_storage_rc:
            # Note that we always begin with a readCurrent of this,
            # to protect concurrent enroll/drop
            return False
        record = self._inst_enrollment_storage[principal_id]
        # again be consistent with the order: remove from the
        # enrollment list then fire the event
        self._drop_record_for_principal_id(record, principal_id)
        del self._inst_enrollment_storage[principal_id]
        return record

    def drop_all(self):
        # pylint: disable=unsubscriptable-object,unsupported-delete-operation
        storage = self._inst_enrollment_storage_rc
        principal_ids = list(storage)
        # watch the order; see drop
        records = list()
        for pid in principal_ids:
            record = storage[pid]
            records.append(record)
            self._drop_record_for_principal_id(record, pid)
            del storage[pid]
        return records
    reset = drop_all


from nti.contenttypes.courses import get_course_vendor_info

from nti.contenttypes.courses.interfaces import IEnrollmentMappedCourseInstance


def get_vendor_info(context):
    result = get_course_vendor_info(context, False) or {}
    return result


def has_deny_open_enrollment(context):
    vendor_info = get_vendor_info(context)
    nti_info = vendor_info.get('NTI', {})
    for name in ('deny_open_enrollment', 'DenyOpenEnrollment'):
        result = nti_info.get(name, None)
        if result is not None:
            return True
    return False


def check_deny_open_enrollment(context):
    """
    Returns a true value if the course disallows open enrollemnt
    """
    vendor_info = get_vendor_info(context)
    nti_info = vendor_info.get('NTI', {})
    for name in ('deny_open_enrollment', 'DenyOpenEnrollment'):
        result = nti_info.get(name, None)
        if result is not None:
            return bool(result)
    return False


def check_enrollment_mapped(context):
    """
    Returns a true value if the course is supposed to be enrollment mapped,
    and passes the tests. Raises an error if it is supposed to be enrollment
    mapped, but fails the tests.
    """
    course = ICourseInstance(context, None)
    vendor_info = get_vendor_info(context)
    if 'NTI' in vendor_info and 'EnrollmentMap' in vendor_info['NTI']:
        result = False
        for scope, data in vendor_info['NTI']['EnrollmentMap'].items():
            result = True
            if scope not in ENROLLMENT_SCOPE_VOCABULARY:
                raise KeyError("Unknown scope", scope)
            if isinstance(data, six.string_types):
                data = {data: sys.maxint}
            # we better get a mapping
            assert isinstance(data, Mapping)
            # validate section and seat count
            # pylint: disable=unsupported-membership-test
            for sec_name, seat_count in data.items():
                if sec_name not in course.SubInstances:
                    raise KeyError("Unknown section", sec_name)
                if not isinstance(seat_count, (int, long)) or seat_count <= 0:
                    raise ValueError("Invalid seat count", sec_name)
        return result


@WithRepr
@total_ordering
@EqHash("section_name")
class SectionSeat(object):

    name = alias('section_name')
    count = alias('seat_count')

    def __init__(self, section_name, seat_count):
        self.seat_count = seat_count
        self.section_name = section_name

    def __lt__(self, other):
        try:
            return (self.section_name, self.seat_count) < (other.section_name, other.seat_count)
        except AttributeError:
            return NotImplemented

    def __gt__(self, other):
        try:
            return (self.section_name, self.seat_count) > (other.section_name, other.seat_count)
        except AttributeError:
            return NotImplemented


def _get_enrollment_map(context):
    result = {}
    vendor_info = get_vendor_info(context)
    if 'NTI' in vendor_info and 'EnrollmentMap' in vendor_info['NTI']:
        for scope, data in vendor_info['NTI']['EnrollmentMap'].items():
            if isinstance(data, six.string_types):
                data = {data: sys.maxint}
            result[scope] = data
    return result


def _find_mapped_course_for_scope(course, scope):
    enrollment_map = _get_enrollment_map(course)
    section_data = enrollment_map.get(scope)
    if section_data:
        items = []
        for section_name in section_data.keys():
            # fail loudly rather than silently enroll in the wrong place
            section = course.SubInstances[section_name]
            # pylint: disable=too-many-function-args
            enrollment_count = ICourseEnrollments(section).count_enrollments()
            items.append(SectionSeat(section_name, enrollment_count))
        # sort by lowest section name, seat count
        # fill one section at a time
        items.sort()
        section = None
        for item in items:
            section_name, estimated_seat_count = item.section_name, item.seat_count
            max_seat_count = section_data[section_name]
            if estimated_seat_count < max_seat_count:
                return course.SubInstances[section_name]

        # could not find a section simply pick at random
        index = random.randint(0, len(items) - 1)
        section_name = items[index].section_name
        section = course.SubInstances[section_name]
        logger.warning("Seat count exceed for section %s",
                       section_name)
        return section

    return course


@component.adapter(IEnrollmentMappedCourseInstance)
@interface.implementer(ICourseEnrollmentManager)
class EnrollmentMappedCourseEnrollmentManager(DefaultCourseEnrollmentManager):
    """
    Handles mapping to an actual course enrollment manager
    for particular scopes.
    """

    def enroll(self, principal, scope=ES_PUBLIC, context=None):
        mapped_course = _find_mapped_course_for_scope(self.context, scope)
        if mapped_course is not self.context:
            manager = (component.getMultiAdapter((mapped_course, self.request),
                                                 ICourseEnrollmentManager)
                       if self.request is not None
                       else ICourseEnrollmentManager(mapped_course))
            return manager.enroll(principal, scope=scope, context=context)

        return super(EnrollmentMappedCourseEnrollmentManager, self).enroll(principal,
                                                                           scope=scope,
                                                                           context=context)

    # Dropping does nothing special: we never get here if we
    # didn't actually wind up enrolling in this course instance itself
    # to start with.


from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectModifiedEvent)
def on_modified_potentially_move_courses(record, _):
    """
    If a user moves between scopes in an enrollment-mapped course,
    we may need to transfer them to a different section too.
    """
    course = record.CourseInstance
    if not IEnrollmentMappedCourseInstance.providedBy(course):
        return
    mapped_course = _find_mapped_course_for_scope(course, record.Scope)
    if mapped_course is not course:
        # ok, we have to move you. This will change sharing; since this
        # was a modified event that by definition is changing scopes,
        # the code in sharing.py will also be firing to change the sharing,
        # and we can't know what order that will happen in, so the code
        # has to be robust to that.
        dest_enrollments = IDefaultCourseInstanceEnrollmentStorage(mapped_course)
        mover = IObjectMover(record)
        mover.moveTo(dest_enrollments)


from nti.dataserver.interfaces import IEntity
from nti.dataserver.interfaces import IEntityContainer
from nti.dataserver.interfaces import ILengthEnumerableEntityContainer


@NoPickle
@component.adapter(ICourseInstance)
@interface.implementer(ICourseEnrollments)
class DefaultCourseEnrollments(object):

    def __init__(self, context):
        self.context = context

    @Lazy
    def _inst_enrollment_storage(self):
        # This is a READ ONLY interface, modifications go
        # through the enrollment manager. Therefore we MUST NOT
        # attempt to readCurrent or add to connections
        return IDefaultCourseInstanceEnrollmentStorage(self.context)

    def iter_principals(self):
        # pylint: disable=no-member
        return self._inst_enrollment_storage.keys()

    def iter_enrollments(self):
        # pylint: disable=no-member
        return self._inst_enrollment_storage.values()

    def count_enrollments(self):
        # pylint: disable=no-member
        # Only return enrollment record count with non-deleted principals.
        # We should be clearing that up on user deletion; remove weak ref resolving
        return len(self._inst_enrollment_storage)

    def is_principal_enrolled(self, principal):
        principal_id = IPrincipal(principal).id
        # pylint: disable=unsupported-membership-test
        return principal_id in self._inst_enrollment_storage

    def get_enrollment_for_principal(self, principal):
        # pylint: disable=no-member
        principal_id = IPrincipal(principal).id
        return self._inst_enrollment_storage.get(principal_id)

    # Non-interface methods for legacy compatibility

    def _count_in_scope_without_instructors(self, scope_name):
        scope = self.context.SharingScopes[scope_name]
        len_scope = len(ILengthEnumerableEntityContainer(scope))
        container = IEntityContainer(scope)

        for instructor in self.context.instructors:
            instructor_entity = IEntity(instructor)
            if instructor_entity in container:
                len_scope -= 1
        return len_scope

    # If we really wanted to, we could cache these persistently on the
    # enrollment storage object.

    @cachedIn('_v_count_scope_enrollments')
    def count_scope_enrollments(self, scope):
        # pylint: disable=no-member
        instructor_usernames = {x.id.lower() for x in self.context.instructors}
        # This might not be very performant
        def include_record(record):
            return  record.Principal is not None \
                and record.Scope == scope \
                and record.Principal.id.lower() not in instructor_usernames
        return len([x for x in self._inst_enrollment_storage.values()
                    if include_record(x)])


    @cachedIn('_v_count_credit_enrollments')
    def count_legacy_forcredit_enrollments(self):
        return self._count_in_scope_without_instructors(ES_CREDIT)

    @cachedIn('_v_count_open_enrollments')
    def count_legacy_open_enrollments(self):
        credit_count = self.count_legacy_forcredit_enrollments()
        public_count = self._count_in_scope_without_instructors(ES_PUBLIC)
        return public_count - credit_count


@NoPickle
@interface.implementer(IPrincipalEnrollments)
class DefaultPrincipalEnrollments(object):

    def __init__(self, principal):
        self.principal = principal

    @CachedProperty
    def _all_enrollments(self):
        return list(self._query_enrollments())

    def iter_enrollments(self):
        return iter(self._all_enrollments)

    def count_enrollments(self):
        return len(self._all_enrollments)

    def _query_enrollments(self):
        iprincipal = IPrincipal(self.principal, None)
        if iprincipal is None:
            return

        principal_id = iprincipal.id
        # See comments in catalog.py about queryNextUtility
        catalogs = component.getAllUtilitiesRegisteredFor(ICourseCatalog)
        catalogs = reversed(catalogs)
        seen_cats = []
        seen_storages = []
        seen_records = []

        for catalog in catalogs:
            # Protect against accidentally hitting the same catalog
            # or record multiple times. This can occur (only during tests)
            # if the component registry is manually dorked with. The same storage,
            # however, may be seen multiple times as we walk back up the
            # resolution tree
            if catalog in seen_cats:
                continue
            seen_cats.append(catalog)
            storage = IDefaultCourseCatalogEnrollmentStorage(catalog)
            if storage in seen_storages:
                continue
            seen_storages.append(storage)

        # Now, during migration, we may have put things in a global storage
        # that is not our current global storage. One example:
        # we migrate with the current site platform.ou.edu, but query with the
        # current site janux.ou.edu. Therefore we need to walk up the chain of these
        # guys too. This is not the most elegant approach, but it does work.
        for site_manager in ro.ro(component.getSiteManager()):
            storage = _global_course_catalog_storage(site_manager)
            if storage in seen_storages:
                continue
            seen_storages.append(storage)

        for storage in seen_storages:
            if storage is None:
                continue

            if principal_id in storage:
                for record in storage[principal_id]:
                    if record in seen_records:
                        continue
                    seen_records.append(record)

                    # If the course instance is gone, don't pretend to be enrolled
                    # because most things depend on getting the course from the
                    # enrollment. This is a database consistency problem,
                    # only seen in alpha...being cleaned up as encountered,
                    # so eventually this code can be removed
                    try:
                        ICourseInstance(record)
                    except TypeError:
                        logger.warning("Course for enrollment %r of user %s in storage %s missing. "
                                       "Database consistency issue.",
                                       record, principal_id, storage)
                    else:
                        yield record


from nti.dataserver.interfaces import IUser


@interface.implementer(ICourseInstanceEnrollmentRecord, IContentTypeAware)
class DefaultCourseInstanceEnrollmentRecord(SchemaConfigured,
                                            PersistentCreatedAndModifiedTimeObject):
    """
    Persistent implementation of a enrollment record.

    We are only used in DefaultEnrollmentManagers because we expect
    to know how we are stored.
    """

    __name__ = None
    __parent__ = None

    parameters = {}
    mime_type = mimeType = 'application/vnd.nextthought.courses.defaultcourseinstanceenrollmentrecord'

    Scope = FieldProperty(ICourseInstanceEnrollmentRecord['Scope'])

    def __init__(self, **kwargs):
        PersistentCreatedAndModifiedTimeObject.__init__(self)
        SchemaConfigured.__init__(self, **kwargs)

    def _get_CourseInstance(self):
        """
        We know we are stored as a child of an annotation of a course.
        """
        try:
            return self.__parent__.__parent__
        except AttributeError:
            return None
    CourseInstance = property(_get_CourseInstance, lambda unused_s, unused_nv: None)

    _principal = None

    def _get_Principal(self):
        return self._principal() if self._principal is not None else None

    def _set_Principal(self, nv):
        if nv is None:
            if self._principal is not None:
                del self._principal
        else:
            self._principal = IWeakRef(nv)
    Principal = property(_get_Principal, _set_Principal)

    Creator = creator = alias('Principal')

    def __eq__(self, other):
        try:
            return self is other or (self.__name__, self.__parent__) == (other.__name__, other.__parent__)
        except AttributeError:
            return NotImplemented

    def _ne__(self, other):
        try:
            return self is not other and (self.__name__, self.__parent__) != (other.__name__, other.__parent__)
        except AttributeError:
            return NotImplemented

    def __conform__(self, iface):
        if ICourseInstance.isOrExtends(iface):
            return self.CourseInstance

        if IPrincipal.isOrExtends(iface) or IUser.isOrExtends(iface):
            return self.Principal

# Subscribers to keep things in sync when
# objects are deleted.
# We may have intid-weak references to these things,
# so we need to catch them on the IntIdRemoved event
# for dependable ordering


from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.index import IX_USERNAME


def remove_user_enroll_data(principal):
    """
    remove all enrollment records for the specified principal
    """
    if IPrincipal.providedBy(principal):
        username = principal.id
    elif IUser.providedBy(principal):
        username = principal.username
    else:
        username = str(principal)
    logger.info("Removing enrollment records for %s", username)
    catalog = get_enrollment_catalog()
    intids = component.getUtility(IIntIds)
    query = {
        IX_USERNAME: {'any_of': (username,)}
    }
    for uid in tuple(catalog.apply(query) or ()):  # mutating
        context = intids.queryObject(uid)
        if ICourseInstanceEnrollmentRecord.providedBy(context):
            course = ICourseInstance(context, None)
            manager = ICourseEnrollmentManager(course, None)
            if manager is not None:
                # pylint: disable=too-many-function-args
                manager.drop(principal)


@component.adapter(IUser, IBeforeIdRemovedEvent)
@component.adapter(IPrincipal, IBeforeIdRemovedEvent)
def on_principal_deletion_unenroll(principal, unused_event=None):
    endInteraction()
    try:
        remove_user_enroll_data(principal)
    finally:
        restoreInteraction()


@component.adapter(ICourseInstance, IBeforeIdRemovedEvent)
def on_course_deletion_unenroll(course, event):
    # pylint: disable=unused-variable
    __traceback_info__ = course, event
    # pylint: disable=too-many-function-args
    manager = ICourseEnrollmentManager(course)
    dropped_records = manager.drop_all()
    logger.info("Dropped %d enrollment records on deletion of %r",
                len(dropped_records), course)

    enrollments = ICourseEnrollments(course)
    if enrollments.count_enrollments():
        raise ValueError("Failed to delete all enrollment records from course."
                         " To continue, please restore the course data on disk.",
                         course,
                         list(enrollments.iter_enrollments()))

# Moving enrollments


from zope.copypastemove.interfaces import IObjectMover


def migrate_enrollments_from_course_to_course(source, dest, verbose=False, result=None):
    """
    Move all the enrollments from the ``source`` course to the ``dest``
    course. Sharing will be updated, but no emails will be sent.

    This is safe to run repeatedly. The destination course does not
    have to be empty of enrollments. However, if a principal from the
    source is enrolled in the destination course already,
    *nothing will be changed*: this implies that his record was either
    already moved and he re-enrolled in the source course, or he already
    independently enrolled in the destination course.

    :return: A value that can be used like a boolean to say if
            any enrollments migrated.
    """

    count = 0
    result = list() if result is None else result
    log = logger.debug if not verbose else logger.info

    log('Moving enrollment records from %s to %s',
        ICourseCatalogEntry(source).ntiid,
        ICourseCatalogEntry(dest).ntiid)

    # All we need to do is use IObjectMover to transport the
    # EnrollmentRecord objects; they find their course from
    # where they are located, and the Storage object is a simple
    # IContainer. The sharing listeners take care of the rest.

    dest_enrollments = IDefaultCourseInstanceEnrollmentStorage(dest)
    source_enrollments = IDefaultCourseInstanceEnrollmentStorage(source)

    for source_prin_id in list(source_enrollments):  # copy, we're mutating
        if not source_prin_id or source_prin_id in dest_enrollments:
            log("Ignoring dup enrollment for %s", source_prin_id)
            continue

        source_enrollment = source_enrollments[source_prin_id]
        if IPrincipal(source_enrollment.Principal, None) is None:
            log("Ignoring dup enrollment for %s", source_prin_id)
            continue

        mover = IObjectMover(source_enrollment)
        mover.moveTo(dest_enrollments)
        result.append(source_prin_id)

        log('Enrollment record for %s (scope=%s) moved',
            source_prin_id, source_enrollment.Scope)

        count += 1

    log('%s enrollment record(s) moved', count)
    return count

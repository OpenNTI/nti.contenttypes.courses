#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from datetime import datetime

from itertools import chain

from six import string_types

from ZODB.POSException import POSError

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.catalog.catalog import ResultSet

from zope.component.hooks import getSite

from zope.interface.interfaces import ComponentLookupError

from zope.container.contained import Contained

from zope.index.text.parsetree import ParseError

from zope.intid.interfaces import IIntIds

from zope.location import LocationIterator

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.base.mixins import CreatedAndModifiedTimeMixin

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IEditableContentPackage

from nti.contenttypes.courses.common import get_course_site
from nti.contenttypes.courses.common import get_course_packages
from nti.contenttypes.courses.common import get_course_editors
from nti.contenttypes.courses.common import get_course_instructors
from nti.contenttypes.courses.common import get_instructors_in_roles

from nti.contenttypes.courses.index import IX_TAGS
from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_NAME
from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import IX_ENTRY
from nti.contenttypes.courses.index import IX_COURSE
from nti.contenttypes.courses.index import IX_TOPICS
from nti.contenttypes.courses.index import IX_PACKAGES
from nti.contenttypes.courses.index import IX_USERNAME
from nti.contenttypes.courses.index import IX_ENTRY_PUID
from nti.contenttypes.courses.index import IX_ENTRY_DESC
from nti.contenttypes.courses.index import IX_IMPORT_HASH
from nti.contenttypes.courses.index import IX_ENTRY_TITLE
from nti.contenttypes.courses.index import IX_CONTENT_UNIT
from nti.contenttypes.courses.index import IX_COURSE_INSTRUCTOR
from nti.contenttypes.courses.index import IX_COURSE_EDITOR
from nti.contenttypes.courses.index import IX_ENTRY_END_DATE
from nti.contenttypes.courses.index import IX_ENTRY_START_DATE
from nti.contenttypes.courses.index import IX_COURSE_TO_ENTRY_INTID
from nti.contenttypes.courses.index import IX_ENTRY_TO_COURSE_INTID
from nti.contenttypes.courses.index import TP_DELETED_COURSES
from nti.contenttypes.courses.index import TP_NON_PUBLIC_COURSES

from nti.contenttypes.courses.index import IndexRecord
from nti.contenttypes.courses.index import get_courses_catalog
from nti.contenttypes.courses.index import get_enrollment_catalog
from nti.contenttypes.courses.index import get_course_outline_catalog

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import EDITOR
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_NAMES

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import IDeletedCourse
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord
from nti.contenttypes.courses.interfaces import ICourseCatalogEntryFilterUtility

from nti.contenttypes.courses.vendorinfo import VENDOR_INFO_KEY

from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import CONTENT_ROLE_PREFIX

from nti.dataserver.authorization import is_site_admin
from nti.dataserver.authorization import is_admin_or_site_admin
from nti.dataserver.authorization import role_for_providers_content

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IMutableGroupMember

from nti.dataserver.users.users import User

from nti.ntiids.ntiids import get_parts

from nti.site.hostpolicy import get_host_site

from nti.site.localutility import queryNextUtility

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)

get_instructors_in_roles = get_instructors_in_roles
get_course_instructors = get_course_instructors


class AbstractInstanceWrapper(Contained):

    __acl__ = ()

    def __init__(self, context):
        self.CourseInstance = context
        # Sometimes the CourseInstance object goes away
        # for externalization, so capture an extra copy
        self._private_course_instance = context

    @Lazy
    def __name__(self):
        try:
            # We probably want a better value than `ntiid`? Human readable?
            # or is this supposed to be traversable?
            return ICourseCatalogEntry(self._private_course_instance).ntiid
        # Hmm, the catalog entry is gone, something doesn't match. What?
        except TypeError:
            logger.warning("Failed to get name from catalog for %s/%s",
                           self._private_course_instance,
                           self._private_course_instance.__name__)
            return self._private_course_instance.__name__

    def __conform__(self, iface):
        if ICourseInstance.isOrExtends(iface):
            return self._private_course_instance


# vendor info


def get_course_vendor_info(context, create=True):
    result = None
    course = ICourseInstance(context, None)
    if create:
        result = ICourseInstanceVendorInfo(context, None)
    elif course is not None:
        try:
            annotations = course.__annotations__
            result = annotations.get(VENDOR_INFO_KEY, None)
        except AttributeError:
            pass
    return result


def get_sites_4_index(sites=None):
    if not sites and getSite() is not None:
        sites = get_component_hierarchy_names()
    sites = sites.split() if isinstance(sites, string_types) else sites
    return sites


def get_current_site():
    return getattr(getSite(), '__name__', None)


# index


def index_course_instance(course):
    catalog = get_courses_catalog()
    intids = component.queryUtility(IIntIds)
    if catalog is not None and intids is not None:
        doc_id = intids.queryId(course)
        if doc_id is not None:
            catalog.index_doc(doc_id, course)


def get_courses_for_packages(packages=(), sites=(), intids=None):
    result = set()
    catalog = get_courses_catalog()
    sites = get_sites_4_index(sites)
    if isinstance(packages, string_types):
        packages = packages.split()
    query = {
        IX_SITE: {'any_of': sites},
        IX_PACKAGES: {'any_of': packages}
    }
    intids = component.getUtility(IIntIds) if intids is None else intids
    for uid in catalog.apply(query) or ():
        course = ICourseInstance(intids.queryObject(uid), None)
        result.add(course)
    result.discard(None)
    return tuple(result)


def unindex_course_roles(context, catalog=None):
    course = ICourseInstance(context, None)
    entry = ICourseCatalogEntry(course, None)
    catalog = get_enrollment_catalog() if catalog is None else catalog
    if entry is not None:  # remove all instructors
        site = get_current_site() or ''
        query = {
            IX_SITE: {'any_of': (site,)},
            IX_COURSE: {'any_of': (entry.ntiid,)},
            IX_SCOPE: {'any_of': (INSTRUCTOR, EDITOR, RID_TA)}
        }
        for uid in catalog.apply(query) or ():
            catalog.unindex_doc(uid)


def unindex_user_course_role(user, course, role):
    intids = component.getUtility(IIntIds)
    entry = ICourseCatalogEntry(course, None)
    doc_id = intids.queryId(course)
    if doc_id is not None:
        user = getattr(user, 'id', user)
        user = getattr(user, 'username', user)
        query = {
            IX_SCOPE: {'any_of': (role,)},
            IX_USERNAME: {'any_of': (user,)},
            IX_COURSE: {'any_of': (entry.ntiid,)},
        }
        catalog = get_enrollment_catalog()
        for uid in catalog.apply(query) or ():
            if uid == doc_id:
                catalog.unindex_doc(uid)


def index_course_instructors(course, catalog, entry, doc_id):
    result = 0
    for instructor in course.instructors or ():
        principal = IPrincipal(instructor, None)
        if principal is None:
            continue
        pid = principal.id
        record = IndexRecord(pid, entry.ntiid, INSTRUCTOR)
        catalog.index_doc(doc_id, record)
        result += 1
    return result


def index_user_course_role(user, course, role, site=None):
    intids = component.getUtility(IIntIds)
    entry = ICourseCatalogEntry(course, None)
    doc_id = intids.queryId(course)
    if doc_id is None:
        return 0
    catalog = get_enrollment_catalog()
    principal = IPrincipal(user, None)
    if principal is not None:
        pid = principal.id
        site = site or get_current_site()
        record = IndexRecord(pid, entry.ntiid, role, site)
        catalog.index_doc(doc_id, record)


def index_course_instructor(user, course, role=INSTRUCTOR, site=None):
    index_user_course_role(user, course, role, site)


def index_course_editor(user, course, site=None):
    index_user_course_role(user, course, EDITOR, site)


def index_course_editors(course, catalog, entry, doc_id, site=None):
    result = 0
    for editor in get_course_editors(course) or ():
        principal = IPrincipal(editor, None)
        if principal is None:
            continue
        pid = principal.id
        record = IndexRecord(pid, entry.ntiid, EDITOR, site)
        catalog.index_doc(doc_id, record)
        result += 1
    return result


def index_course_roles(context, catalog=None, intids=None):
    course = ICourseInstance(context, None)
    entry = ICourseCatalogEntry(context, None)
    if entry is None:
        return 0
    catalog = get_enrollment_catalog() if catalog is None else catalog
    intids = component.getUtility(IIntIds) if intids is None else intids
    doc_id = intids.queryId(course)
    if doc_id is None:
        return 0
    result = 0
    result += index_course_editors(course, catalog, entry, doc_id)
    result += index_course_instructors(course, catalog, entry, doc_id)
    index_course_instance(course)
    return result


def unindex_course_instructor(user, course, role=INSTRUCTOR):
    unindex_user_course_role(user, course, role)


# course & hierarchy


def get_parent_course(context):
    course = ICourseInstance(context, None)
    if ICourseSubInstance.providedBy(course):
        course = course.__parent__.__parent__
    return course


def get_course_subinstances(context):
    course = ICourseInstance(context, None)
    if course is not None and not ICourseSubInstance.providedBy(course):
        # pylint: disable=no-member
        return tuple(course.SubInstances.values())
    return ()


def get_course_hierarchy(context):
    result = []
    parent = get_parent_course(context)
    if parent is not None:
        # pylint: disable=no-member
        result.append(parent)
        result.extend(parent.SubInstances.values())
    return result


def get_content_unit_courses(context, include_sub_instances=True):
    result = ()
    unit = IContentUnit(context, None)
    package = find_interface(unit, IContentPackage, strict=False)
    if package is not None:
        courses = get_courses_for_packages(packages=package.ntiid)
        if not include_sub_instances:
            result = tuple(
                x for x in courses if not ICourseSubInstance.providedBy(x)
            )
        else:
            result = courses
    return result
content_unit_to_courses = get_content_unit_courses


# enrollments


def is_there_an_open_enrollment(course, user):
    if user is None:
        return False
    for instance in get_course_hierarchy(course):
        enrollments = ICourseEnrollments(instance)
        # pylint: disable=too-many-function-args
        record = enrollments.get_enrollment_for_principal(user)
        if record is not None and record.Scope == ES_PUBLIC:
            return True
    return False


def get_enrollment_in_hierarchy(course, user):
    if user is None:
        return None
    for instance in get_course_hierarchy(course):
        enrollments = ICourseEnrollments(instance)
        # pylint: disable=too-many-function-args
        record = enrollments.get_enrollment_for_principal(user)
        if record is not None:
            return record
    return None
get_any_enrollment = get_enrollment_in_hierarchy


def drop_any_other_enrollments(context, user, ignore_existing=True):
    result = []
    main_course = ICourseInstance(context)
    main_entry = ICourseCatalogEntry(main_course)
    for instance in get_course_hierarchy(main_course):
        instance_entry = ICourseCatalogEntry(instance)
        if ignore_existing and main_entry.ntiid == instance_entry.ntiid:
            continue
        # pylint: disable=too-many-function-args
        enrollments = ICourseEnrollments(instance)
        enrollment = enrollments.get_enrollment_for_principal(user)
        if enrollment is not None:
            enrollment_manager = ICourseEnrollmentManager(instance)
            enrollment_manager.drop(user)
            entry = ICourseCatalogEntry(instance, None)
            logger.warning("User %s dropped from course '%s' open enrollment",
                           user, getattr(entry, 'ProviderUniqueID', None))
            result.append(instance)
    return result


def get_catalog_entry(ntiid, safe=True):
    try:
        catalog = component.getUtility(ICourseCatalog)
        entry = catalog.getCatalogEntry(ntiid) if ntiid else None
        return entry
    except (ComponentLookupError, KeyError) as e:
        if not safe:
            raise e
    return None


def get_enrollment_record(context, user):
    course = ICourseInstance(context, None)
    enrollments = ICourseEnrollments(course, None)
    if user is not None and enrollments is not None:
        # pylint: disable=too-many-function-args
        return enrollments.get_enrollment_for_principal(user)
    return None


def get_enrollment_record_in_hierarchy(context, user):
    for instance in get_course_hierarchy(context):
        record = get_enrollment_record(instance, user)
        if record is not None:
            return record
    return None


def is_enrolled(context, user):
    course = ICourseInstance(context, None)
    enrollments = ICourseEnrollments(course, None)
    if user is not None and enrollments is not None:
        # pylint: disable=too-many-function-args
        return enrollments.is_principal_enrolled(user)
    return False


def is_enrolled_in_hierarchy(context, user):
    for instance in get_course_hierarchy(context):
        if is_enrolled(instance, user):
            return True
    return False


def get_course_enrollments(context, sites=None, intids=None):
    if     ICourseInstance.providedBy(context) \
        or ICourseCatalogEntry.providedBy(context):
        entry = ICourseCatalogEntry(context, None)
        if entry is None:
            return ()
        courses = (entry.ntiid,)
        sites = get_course_site(ICourseInstance(context))
    elif isinstance(context, string_types):
        courses = context.split()
    else:
        courses = context
    result = []
    sites = get_sites_4_index(sites)
    catalog = get_enrollment_catalog()
    intids = component.getUtility(IIntIds) if intids is None else intids
    query = {
        IX_SITE: {'any_of': sites},
        IX_COURSE: {'any_of': courses},
        IX_SCOPE: {'any_of': ENROLLMENT_SCOPE_NAMES}
    }
    for doc_id in catalog.apply(query) or ():
        obj = intids.queryObject(doc_id)
        if     ICourseInstanceEnrollmentRecord.providedBy(obj) \
            or ICourseInstance.providedBy(obj):
            result.append(obj)
    return result


def get_courses_for_scope(user, scopes=(), sites=None, intids=None):
    """
    Fetch the enrollment records for the given user (or username)
    and the given enrollment scopes, including instructor/editor scopes.
    """
    result = []
    intids = component.getUtility(IIntIds) if intids is None else intids
    catalog = get_enrollment_catalog()
    sites = get_sites_4_index(sites)
    username = getattr(user, 'username', user)
    query = {
        IX_SCOPE: {'any_of': scopes},
        IX_USERNAME: {'any_of': (username,)},
    }
    if sites:
        query[IX_SITE] = {'any_of': sites}
    for doc_id in catalog.apply(query) or ():
        obj = intids.queryObject(doc_id)
        if     ICourseInstanceEnrollmentRecord.providedBy(obj) \
            or (    ICourseInstance.providedBy(obj)
                and not IDeletedCourse.providedBy(obj)):
            result.append(obj)
    return result
_get_courses_for_scope = get_courses_for_scope


def get_enrollments(user, **kwargs):
    """
    Returns an iterable containing all the courses
    in which this user is enrolled
    """
    return get_courses_for_scope(user,
                                 scopes=ENROLLMENT_SCOPE_NAMES,
                                 **kwargs)


def get_non_preview_enrollments(user, **kwargs):
    """
    Returns an iterable containing all the non-preview enrollment records
    for this user.
    """
    records = get_enrollments(user, **kwargs)
    result = []
    for record in records:
        course = ICourseInstance(record, None)
        entry = ICourseCatalogEntry(course, None)
        if entry is not None and not entry.Preview:
            result.append(record)
    return result


def has_enrollments(user, intids=None):
    for obj in get_enrollments(user, intids=intids):
        if ICourseInstanceEnrollmentRecord.providedBy(obj):
            return True
    return False


@interface.implementer(ICourseInstanceEnrollmentRecord)
class ProxyEnrollmentRecord(CreatedAndModifiedTimeMixin, Contained):

    Scope = None
    Principal = None
    CourseInstance = None

    _SET_CREATED_MODTIME_ON_INIT = False

    def __init__(self, course=None, principal=None, scope=None):
        CreatedAndModifiedTimeMixin.__init__(self)
        self.Scope = scope
        self.Principal = principal
        self.CourseInstance = course


def get_user_or_instructor_enrollment_record(context, user):
    """
    Fetches an enrollment record for the given context/user,
    returning a pseudo-record with an `ES_ALL` scope if the
    user is an instructor/editor.
    """
    course = ICourseInstance(context, None)  # e.g. course in lineage
    if course is None:
        return None
    else:
        is_editor = has_permission(ACT_CONTENT_EDIT, course, user.username)
        # give priority to course in lineage before checking the rest
        for instance in get_course_hierarchy(course):
            if is_course_instructor_or_editor(instance, user) or is_editor:
                # create a fake enrollment record w/ all scopes to signal an
                # instructor
                return ProxyEnrollmentRecord(course, IPrincipal(user), ES_ALL)
        # find any enrollment
        return get_any_enrollment(course, user)


# instructors & editors


def _get_instructors_or_editors(site, indexes, excludedCourse=None):
    """
    Fetch all course instructors or all course editors for the given site,

    If no site is provided, courses for the site hierarchy will be checked.

    If excludedCourse is provided, it won't return instructors/editors for
    that course.
    """
    intids = component.getUtility(IIntIds)
    catalog = get_courses_catalog()
    if site is not None:
        sites = (getattr(site, '__name__', site),)
    else:
        sites = get_sites_4_index(site)
    query = {
        IX_SITE: {'any_of': sites}
    }
    admin_indexes = list()
    for idx in indexes:
        admin_index = catalog[idx]
        admin_indexes.append(admin_index)

    excludedIntid = intids.queryId(excludedCourse) if excludedCourse is not None else None

    usernames = set()
    # First gather all courses for our site, then get the
    # set of usernames for the index(es) for each course.
    for doc_id in catalog.apply(query) or ():
        if excludedIntid is not None and doc_id == excludedIntid:
            continue
        for idx in admin_indexes:
            admin_usernames = idx.values(doc_id=doc_id)
            if admin_usernames:
                usernames.update(admin_usernames)

    result = list()
    for username in usernames:
        user = User.get_user(username)
        if user is not None:
            result.append(user)
    return result


def get_instructors_and_editors(site=None):
    """
    Return an iterable of unique instructor and editor users
    for the current site.
    """
    return _get_instructors_or_editors(site=site,
                                       indexes=(IX_COURSE_INSTRUCTOR, IX_COURSE_EDITOR))


def get_instructors(site=None, excludedCourse=None):
    return _get_instructors_or_editors(site=site,
                                       indexes=(IX_COURSE_INSTRUCTOR,),
                                       excludedCourse=excludedCourse)


def get_editors(site=None, excludedCourse=None):
    return _get_instructors_or_editors(site=site,
                                       indexes=(IX_COURSE_EDITOR,),
                                       excludedCourse=excludedCourse)


def get_all_site_course_intids(site=None):
    """
    Return all course intids for all courses in the site hierarchy.
    """
    catalog = get_courses_catalog()
    sites = get_sites_4_index(site)
    # This contains course catalog entries and course instances.
    # We intersect with name since that contains only courses. The `name`
    # here is `__name__`, which should always be none-null for real courses.
    query = {IX_SITE: {'any_of': sites},
             IX_NAME: {'any': None}}
    return catalog.apply(query)


def get_all_site_entry_intids(site=None, exclude_non_public=False, exclude_deleted=True):
    """
    Return all course catalog entry intids for all courses in the site hierarchy,
    optionally excluding deleted and/or non_public.

    FIXME: mimic this in course function
    """
    catalog = get_courses_catalog()
    query = {IX_ENTRY_TO_COURSE_INTID: {'any': None}}
    sites = get_sites_4_index(site)
    if sites:
        query[IX_SITE] = {'any_of': sites}
    rs = catalog.apply(query)
    if exclude_deleted:
        deleted_intids_extent = catalog[IX_TOPICS][TP_DELETED_COURSES].getExtent()
        rs = rs - deleted_intids_extent
    if exclude_non_public:
        nonpublic_intids_extent = catalog[IX_TOPICS][TP_NON_PUBLIC_COURSES].getExtent()
        rs = rs - nonpublic_intids_extent
    return rs


def get_site_course_admin_intids_for_user(user, site=None):
    """
    For the given site admin, return all applicable course intids.
    This will include all courses for the site admin as well as
    any instructed courses (may be from the parent site).
    """
    catalog = get_courses_catalog()
    sites = get_sites_4_index(site)
    query_sites = list()
    for site_name in sites:
        site_for_site_name = get_host_site(site_name)
        if is_site_admin(user, site_for_site_name):
            query_sites.append(site_name)
    result_sets = []
    if query_sites:
        # Do not want to pass in empty list here - since this user is
        # not a site admin.
        sites_course_intids = get_all_site_course_intids(query_sites)
        result_sets.append(sites_course_intids)
    instructor_intids = get_instructed_courses_intids(user)
    result_sets.append(instructor_intids)
    editor_intids = get_edited_courses_intids(user)
    result_sets.append(editor_intids)
    return catalog.family.IF.multiunion(result_sets)


def _get_course_admin_intids_for_user(user, idx, site=None):
    """
    Return the set of course intids the given user administers
    (instructor or editor).
    """
    catalog = get_courses_catalog()
    username = getattr(user, 'username', user)
    if site is not None:
        sites = (getattr(site, '__name__', site),)
    else:
        sites = get_sites_4_index(site)
    query = {
        idx: {'any_of': (username,)}
    }
    if sites:
        query[IX_SITE] = {'any_of': sites}
    return catalog.apply(query)


def get_instructed_courses_intids(user, site=None):
    """
    Returns an iterable containing all the course intids
    in which this user is an instructor.
    """
    return _get_course_admin_intids_for_user(user,
                                             IX_COURSE_INSTRUCTOR,
                                             site=site)


def get_edited_courses_intids(user, site=None):
    """
    Returns an iterable containing all the course intids
    in which this user is an editor.
    """
    return _get_course_admin_intids_for_user(user,
                                             IX_COURSE_EDITOR,
                                             site=site)


def has_instructed_courses(user):
    """
    Return a bool if this user instructs any courses.
    """
    return bool(get_instructed_courses_intids(user))


def has_edited_courses(user):
    """
    Return a bool if this user acts as an editor for any courses.
    """
    return bool(get_edited_courses_intids(user))


def get_instructed_courses(user):
    """
    Returns an iterable containing all the courses
    in which this user is an instructor.
    """
    intids = component.getUtility(IIntIds)
    rs = get_instructed_courses_intids(user)
    result = []
    for intid in rs:
        obj = intids.queryObject(intid)
        if ICourseInstance.providedBy(obj):
            result.append(obj)
    return result


def get_edited_courses(user):
    """
    Returns an iterable containing all the courses
    in which this user is an editor.
    """
    intids = component.getUtility(IIntIds)
    rs = get_edited_courses_intids(user)
    result = []
    for intid in rs:
        obj = intids.queryObject(intid)
        if ICourseInstance.providedBy(obj):
            result.append(obj)
    return result


def get_instructed_and_edited_courses(user):
    """
    Returns an iterable containing all the courses in which this user is
    either an instructor or an editor.
    """
    result = set()
    instructed_courses = get_instructed_courses(user)
    result.update(instructed_courses)
    edited_courses = get_edited_courses(user)
    result.update(edited_courses)
    return result


def is_course_instructor(context, user):
    result = False
    prin = IPrincipal(user, None)
    course = ICourseInstance(context, None)
    roles = IPrincipalRoleMap(course, None)
    if roles and prin:
        result = Allow in (roles.getSetting(RID_TA, prin.id),
                           roles.getSetting(RID_INSTRUCTOR, prin.id))
    return result


def course_locator(context):
    for x in LocationIterator(context):
        course = ICourseInstance(x, None)
        if course is not None:
            return course
    return None


def is_instructed_by_name(context, username):
    """
    Checks if the context is within something instructed
    by the given principal id. The context will be searched
    for an ICourseInstance.

    If either the context or username is missing, returns
    a false value.
    """

    if username is None or context is None:
        return False

    course = course_locator(context)
    roles = IPrincipalRoleMap(course, None)
    if roles:
        result = Allow in (roles.getSetting(RID_TA, username),
                           roles.getSetting(RID_INSTRUCTOR, username))
        return result
    return False


def is_course_editor(context, user):
    result = False
    prin = IPrincipal(user, None)
    course = ICourseInstance(context, None)
    roles = IPrincipalRoleManager(course, None)
    if roles and prin:
        result = (Allow == roles.getSetting(RID_CONTENT_EDITOR, prin.id))
    return result


def is_edited_by_name(context, username):
    """
    Checks if the context is within something that can be edited
    by the given principal id. The context will be searched
    for an ICourseInstance.

    If either the context or username is missing, returns
    a false value.
    """

    if username is None or context is None:
        return False

    course = course_locator(context)
    roles = IPrincipalRoleMap(course, None)
    if roles:
        result = (Allow == roles.getSetting(RID_CONTENT_EDITOR, username))
        return result
    return False


def is_instructed_or_edited_by_name(context, username):
    if username is None or context is None:
        return False

    course = course_locator(context)
    roles = IPrincipalRoleMap(course, None)
    if roles:
        result = Allow in (roles.getSetting(RID_TA, username),
                           roles.getSetting(RID_INSTRUCTOR, username),
                           roles.getSetting(RID_CONTENT_EDITOR, username))
        return result
    return False


def is_instructor_in_hierarchy(context, user):
    for instance in get_course_hierarchy(context):
        if is_course_instructor(instance, user):
            return True
    return False


def get_instructed_course_in_hierarchy(context, user):
    for instance in get_course_hierarchy(context):
        if is_course_instructor(instance, user):
            return instance
    return None


def is_course_instructor_or_editor(context, user):
    result = is_course_instructor(context, user) \
          or is_course_editor(context, user)
    return result


def get_enrollment_records(usernames=None, entry_ntiids=None, sites=None, intids=None):
    """
    Fetch the enrollment records for the given usernames, and the given course catalog entry ntiids.
    """
    result = []
    intids = component.getUtility(IIntIds) if intids is None else intids
    catalog = get_enrollment_catalog()
    sites = (getSite().__name__,) if sites is None and getSite() is not None else sites
    query = {
        IX_SCOPE: {'any_of': ENROLLMENT_SCOPE_NAMES},
    }
    if usernames:
        query[IX_USERNAME] = {'any_of': usernames}
    if entry_ntiids:
        query[IX_ENTRY] = {'any_of': entry_ntiids}
    if sites:
        query[IX_SITE] = {'any_of': sites}
    for doc_id in catalog.apply(query) or ():
        obj = intids.queryObject(doc_id)
        if ICourseInstanceEnrollmentRecord.providedBy(obj):
            result.append(obj)
    return result


# outlines


def get_content_outline_nodes(ntiid, intids=None):
    catalog = get_course_outline_catalog()
    query = {
        IX_CONTENT_UNIT: {'any_of': (ntiid,)},
    }
    result = set()
    intids = component.getUtility(IIntIds) if intids is None else intids
    for uid in catalog.apply(query) or ():
        node = ICourseOutlineNode(intids.queryObject(uid), None)
        result.add(node)
    result.discard(None)
    return tuple(result)


def unregister_outline_nodes(course, registry=None):
    if registry is None:
        site = get_course_site(course)
        site = get_host_site(site, safe=True) if site else None
        registry = site.getSiteManager() if site is not None else None

    def recur(node):
        for child in node.values():
            recur(child)
        if not ICourseOutline.providedBy(node):
            node_ntiid = getattr(node, 'ntiid', None)
            if node_ntiid:
                unregisterUtility(registry,
                                  name=node.ntiid,
                                  provided=iface_of_node(node))

    if registry is not None and course.Outline:
        recur(course.Outline)


def clear_course_outline(course):
    if course.Outline:
        unregister_outline_nodes(course)
        course.Outline.clear()  # clear outline


def unenroll(record, user):
    try:
        course = record.CourseInstance
        enrollment_manager = ICourseEnrollmentManager(course)
        # pylint: disable=too-many-function-args
        enrollment_manager.drop(user)
    except (TypeError, KeyError):
        pass


def unenroll_instructor(instructor, course):
    """
    Unenroll the instructor from any courses they may have
    pre-emptively enrolled in.
    """
    for course in get_course_hierarchy(course) or ():
        if is_enrolled(course, instructor):
            entry_ntiid = ICourseCatalogEntry(course).ntiid
            manager = ICourseEnrollmentManager(course)
            # pylint: disable=too-many-function-args
            manager.drop(instructor)
            logger.info('Dropping instructor from course (%s) (%s)',
                        instructor, entry_ntiid)


def get_principal(principal):
    try:
        if principal is None or IUser(principal, None) is None:
            principal = None
    except (TypeError, POSError):
        principal = None
    return principal


def adjust_scope_membership(principal, scope, course,
                            join, follow,
                            ignored_exceptions=(),
                            currently_in=(),
                            relevant_scopes=None,
                            related_enrolled_courses=()):
    if principal is not None:
        join = getattr(principal, join)
        follow = getattr(principal, follow)
    else:
        join = follow = None

    scopes = course.SharingScopes

    if relevant_scopes is None:
        relevant_scopes = scopes.getAllScopesImpliedbyScope(scope)

    scopes_to_ignore = []
    for related_course in related_enrolled_courses:
        sharing_scopes = related_course.SharingScopes
        scopes_to_ignore.extend(
            sharing_scopes.getAllScopesImpliedbyScope(scope))

    for scope in relevant_scopes:
        if scope in currently_in or scope in scopes_to_ignore:
            continue
        try:
            if join is not None:
                join(scope)
        except ignored_exceptions:
            pass

        try:
            if follow is not None:
                follow(scope)
        except ignored_exceptions:
            pass


def _content_roles_for_course_instance(course, packages=None):
    """
    Returns the content roles for all the applicable content
    packages in the course, if there are any.

    :return: A set.
    """
    if packages is None:
        packages = get_course_packages(course)
    roles = []
    for pack in packages:
        if pack is None:
            continue
        # Editable content packages may have fluxuating permissible
        # state; so we handle those elsewhere.
        if IEditableContentPackage.providedBy(pack):
            continue
        ntiid = pack.ntiid
        ntiid = get_parts(ntiid)
        provider = ntiid.provider
        specific = ntiid.specific
        roles.append(role_for_providers_content(provider, specific))
    return set(roles)


def add_principal_to_course_content_roles(principal, course, packages=None):
    if get_principal(principal) is None:
        return

    membership = component.getAdapter(principal, IMutableGroupMember,
                                      CONTENT_ROLE_PREFIX)
    orig_groups = set(membership.groups)
    new_groups = _content_roles_for_course_instance(course, packages)

    final_groups = orig_groups | new_groups
    if final_groups != orig_groups:
        # be idempotent
        membership.setGroups(final_groups)


def _get_principal_visible_packages(principal, courses_to_exclude=()):
    """
    Gather the set of packages the principal has access to, excluding any
    courses given.
    """
    result = set()
    enrollments = get_enrollments(principal.username)
    admin_courses = get_instructed_and_edited_courses(principal) or ()
    for record in chain(enrollments, admin_courses):
        course = ICourseInstance(record, None)  # dup enrollment
        if      course is not None \
            and course not in courses_to_exclude:
            packages = get_course_packages(course)
            result.update(packages)
    return result


def remove_principal_from_course_content_roles(principal, course, packages=None,
                                               unenroll=False): # pylint: disable=redefined-outer-name
    """
    Remove the principal from the given course roles (and optional packages).
    We must verify the principal does not have access to this content
    outside of the given course.
    """
    if get_principal(principal) is None:
        return

    if not packages:
        packages = get_course_packages(course)

    if not packages:
        return

    # Only these are viable package roles, because editable packages
    # are not shared between courses currently.
    role_packages = [x for x in packages if not IEditableContentPackage.providedBy(x)]
    if not role_packages:
        return

    courses_to_exclude = (course,) if unenroll else ()

    # Get the minimal set of packages to remove roles for.
    allowed_packages = _get_principal_visible_packages(principal,
                                                       courses_to_exclude=courses_to_exclude)
    to_remove = set(role_packages) - allowed_packages

    roles_to_remove = _content_roles_for_course_instance(course, to_remove)
    membership = component.getAdapter(principal, IMutableGroupMember,
                                      CONTENT_ROLE_PREFIX)
    groups = set(membership.groups)
    new_groups = groups - roles_to_remove
    if new_groups != groups:
        membership.setGroups(new_groups)


def grant_access_to_course(user, course, scope):
    """
    Grant the user access to the course with the given scope.
    """
    adjust_scope_membership(user, scope, course,
                            'record_dynamic_membership',
                            'follow')
    add_principal_to_course_content_roles(user, course)


def principal_is_enrolled_in_related_course(principal, course):
    """
    If the principal is enrolled in a parent or sibling course,
    return those courses.
    """
    result = []
    potential_other_courses = []
    potential_other_courses.extend(course.SubInstances.values())
    if ICourseSubInstance.providedBy(course):
        main_course = get_parent_course(course)
        potential_other_courses.append(main_course)
        potential_other_courses.extend(
            # pylint: disable=no-member
            x for x in main_course.SubInstances.values() if x is not course
        )

    principal = get_principal(principal)
    if principal is not None:
        for other in potential_other_courses:
            enrollments = ICourseEnrollments(other)
            # pylint: disable=too-many-function-args
            if enrollments.get_enrollment_for_principal(principal) is not None:
                result.append(other)
    return result
_principal_is_enrolled_in_related_course = principal_is_enrolled_in_related_course


def deny_access_to_course(user, course, scope):
    """
    Remove the user access to the course with the given scope.
    """
    principal = get_principal(user)

    related_enrolled_courses = \
        principal_is_enrolled_in_related_course(principal, course)

    # If the course was in the process of being deleted,
    # the sharing scopes may already have been deleted, which
    # shouldn't be a problem: the removal listeners for those
    # events should have cleaned up
    adjust_scope_membership(user, scope, course,
                            'record_no_longer_dynamic_member',
                            'stop_following',
                            # Depending on the order, we may have already
                            # cleaned this up (e.g, deleting a principal
                            # fires events twice due to various cleanups)
                            # So the entity may no longer have an intid ->
                            # KeyError
                            ignored_exceptions=(KeyError,),
                            related_enrolled_courses=related_enrolled_courses)

    remove_principal_from_course_content_roles(principal,
                                               course,
                                               unenroll=True)


def grant_instructor_access_to_course(user, course):
    """
    Grant an instructor appropriate access to a course. As a side-effect of
    this, we ensure the user is not enrolled (if necessary).
    """
    unenroll_instructor(user, course)

    # NOTE: Can we re-use some of the access grant that occurs with students?
    add_principal_to_course_content_roles(user, course)
    for scope in course.SharingScopes.values():
        # They're a member...
        user.record_dynamic_membership(scope)
        # ...and they follow it to get notifications of things
        # shared to it
        user.follow(scope)

    # If they're an instructor of a section, give them
    # access to the public community of the main course.
    if ICourseSubInstance.providedBy(course):
        parent_course = get_parent_course(course)
        # pylint: disable=unsubscriptable-object
        public_scope = parent_course.SharingScopes[ES_PUBLIC]
        user.record_dynamic_membership(public_scope)
        user.follow(public_scope)


def deny_instructor_access_to_course(user, course):
    """
    Remove an instructor from accessing the course. Instructors cannot
    be enrolled as students.
    """
    user = IUser(user)

    # by definition here we have an IPrincipal that *came* from an IUser
    # and has a hard reference to it, and so can become an IUser again
    if not is_course_editor(course, user):
        remove_principal_from_course_content_roles(user, course, unenroll=True)
    if not is_enrolled(course, user):
        # Only remove from scopes if not enrolled.
        for scope in course.SharingScopes.values():
            user.record_no_longer_dynamic_member(scope)
            user.stop_following(scope)

        # And remove access to the parent public scope.
        # FIXME: this needs to check parent course instructor access right?
        if ICourseSubInstance.providedBy(course):
            parent_course = get_parent_course(course)
            # pylint: disable=unsubscriptable-object
            public_scope = parent_course.SharingScopes[ES_PUBLIC]
            user.record_no_longer_dynamic_member(public_scope)
            user.stop_following(public_scope)


# catalog entry


def path_for_entry(context):
    parents = []
    o = context.__parent__
    while o is not None and not ICourseCatalog.providedBy(o):
        parents.append(o.__name__)
        o = getattr(o, '__parent__', None)
    parents.reverse()
    if None in parents:
        logger.warning("Unable to get path for %r, missing parents: %r",
                       context, parents)
        return None
    result = u'/'.join(parents) if parents else None
    return result


def get_entry_intids_for_title(title, sites=(), glob=True):
    """
    Given a single title, query the text index.
    Note, we do not do any subinstance work here.

    We return None if the query is invalid.
    """
    if glob:
        title = '*%s*' % title
    catalog = get_courses_catalog()
    query = {IX_ENTRY_TITLE: title}
    sites = get_sites_4_index(sites)
    if sites:
        query[IX_SITE] = {'any_of': sites}
    try:
        return catalog.apply(query)
    except ParseError:
        logger.warn("Invalid catalog search term (%s)", title)


def get_entry_intids_for_desc(description, sites=(), glob=True):
    """
    Given a single description, query the text index.
    Note, we do not do any subinstance work here.

    We return None if the query is invalid.
    """
    if glob:
        description = '*%s*' % description
    catalog = get_courses_catalog()
    query = {IX_ENTRY_DESC: description}
    sites = get_sites_4_index(sites)
    if sites:
        query[IX_SITE] = {'any_of': sites}
    try:
        return catalog.apply(query)
    except ParseError:
        logger.warn("Invalid catalog search term (%s)", description)


def get_entry_intids_for_puid(puid, sites=(), glob=True):
    """
    Given a single puid, query the text index.

    We return None if the query is invalid.
    """
    if glob:
        puid = '*%s*' % puid
    catalog = get_courses_catalog()
    query = {IX_ENTRY_PUID: puid}
    sites = get_sites_4_index(sites)
    if sites:
        query[IX_SITE] = {'any_of': sites}
    try:
        return catalog.apply(query)
    except ParseError:
        logger.warn("Invalid catalog search term (%s)", puid)


def get_entries_for_puid(puid, sites=None, glob=True):
    """
    Given a single puid, return all :class:`ICourseCatalogEntry` objects.
    """
    entry_intids = get_entry_intids_for_puid(puid, sites=sites, glob=glob)
    if entry_intids is None:
        return ()
    intids = component.getUtility(IIntIds)
    rs = ResultSet(entry_intids, intids)
    entries = [x for x in rs if ICourseCatalogEntry.providedBy(x)]
    return entries


def get_courses_for_puid(puid, sites=None, glob=True):
    """
    Given a single puid, return all :class:`ICourseInstance` objects.
    """
    entries = get_entries_for_puid(puid, sites, glob=glob)
    courses = (ICourseInstance(x, None) for x in entries)
    return [x for x in courses if x is not None]


def get_entry_intids_for_tag(tags, sites=()):
    """
    Given a set of tags, get all entries with that tag.
    Note, we do not do any subinstance work here.
    """
    if isinstance(tags, string_types):
        tags = (tags,)
    catalog = get_courses_catalog()
    query = {IX_TAGS: {'any_of': tags}}
    sites = get_sites_4_index(sites)
    if sites:
        query[IX_SITE] = {'any_of': sites}
    return catalog.apply(query)


def get_non_tagged_entry_intids(sites=(), exclude_non_public=True, exclude_deleted=True):
    """
    Return all entry intids that *do not* have any tags.
    """
    catalog = get_courses_catalog()
    query = {IX_TAGS: {'any': None}}
    tagged_intids = catalog.apply(query)
    all_entry_intids = get_all_site_entry_intids(site=sites,
                                                 exclude_non_public=exclude_non_public,
                                                 exclude_deleted=exclude_deleted)
    return catalog.family.IF.difference(all_entry_intids, tagged_intids)


def get_courses_for_tag(tag, sites=(), intids=None):
    """
    Given a tag, get all courses with that tag.
    """
    courses = set()
    intids = component.getUtility(IIntIds) if intids is None else intids
    rs = get_entry_intids_for_tag(tag, sites=sites)
    for uid in rs or ():
        obj = intids.queryObject(uid)
        course = ICourseInstance(obj, None)
        if course is not None:
            courses.add(course)
    result = set()
    # FIXME: remove this
    # CourseSubinstances will inherit the parent's tags unless they are
    # explicitly set; therefore, we mimic that behavior here.
    for course in courses:
        if not ICourseSubInstance.providedBy(course):
            children = get_course_subinstances(course)
            for child in children or ():
                child_entry = ICourseCatalogEntry(child, None)
                # pylint: disable=unsupported-membership-test
                if tag in getattr(child_entry, 'tags', ()):
                    result.add(child)
        result.add(course)
    return tuple(result)


def is_hidden_tag(tag):
    """
    Hidden tags are defined as starting with a '.'.
    """
    return tag.startswith('.')


def filter_hidden_tags(tags):
    """
    Filter any hidden tags from the given set of tags. Hidden tags are defined
    as starting with a '.'.
    """
    if not tags:
        return ()
    return [x for x in tags if not is_hidden_tag(x)]


def get_course_tags(filter_str=None, filter_hidden=True, sites=(),
                    exclude_non_public=True):
    """
    Get all course tags. Optionally filtering by the given `filter_str` param
    and by default, removing all hidden tags.

    Only tags for non-deleted, public courses are returned.

    Returns a dict of tag -> course count.
    """
    catalog = get_courses_catalog()
    tag_index = catalog[IX_TAGS]
    result = dict()
    if filter_str:
        filter_str = filter_str.lower()
    entry_intids = get_all_site_entry_intids(site=sites,
                                             exclude_deleted=True,
                                             exclude_non_public=exclude_non_public)
    for entry_intid in entry_intids:
        course_tags = tag_index._rev_index.get(entry_intid)
        for tag in course_tags or ():
            if filter_hidden and is_hidden_tag(tag):
                continue
            if filter_str and filter_str not in tag:
                continue
            if tag not in result:
                result[tag] = 0
            result[tag] += 1
    return result


def get_context_enrollment_records(user, requesting_user):
    """
    For a requesting_user, fetch all relevant enrollment records for the
    given user.
    """
    result = []
    if is_admin_or_site_admin(requesting_user) or user == requesting_user:
        # Admins get everything
        result = get_enrollments(user)
    elif has_instructed_courses(requesting_user):
        # Instructors get enrollment records for the courses they teach.
        enrolled_courses_to_records = {x.CourseInstance:x for x in get_enrollments(user)}
        instructed_courses = get_instructed_courses(requesting_user)
        for course in instructed_courses or ():
            try:
                record = enrolled_courses_to_records[course]
                result.append(record)
            except KeyError:
                pass
    return result


def get_courses_for_export_hash(export_hash):
    """
    For the given export hash, return all :class:`ICourseInstance` objects
    that were imported with this hash.
    """
    catalog = get_courses_catalog()
    result = set()
    query = {
        IX_IMPORT_HASH: {'any_of': (export_hash,)},
    }
    intids = component.getUtility(IIntIds)
    for uid in catalog.apply(query) or ():
        course = ICourseInstance(intids.queryObject(uid), None)
        result.add(course)
    result.discard(None)
    return tuple(result)


def course_intids_to_entry_intids(course_intids):
    """
    Transmogrifies course_intids to a set of entry_intids.
    """
    catalog = get_courses_catalog()
    query = {
        IX_ENTRY_TO_COURSE_INTID: {'any_of': course_intids},
    }
    return catalog.apply(query)


def entry_intids_to_course_intids(entry_intids):
    """
    Transmogrifies entry_intids to a set of course_intids.
    """
    catalog = get_courses_catalog()
    query = {
        IX_COURSE_TO_ENTRY_INTID: {'any_of': entry_intids},
    }
    return catalog.apply(query)


@interface.implementer(ICourseCatalogEntryFilterUtility)
class CourseCatalogEntryFilterUtility(object):
    """
    A utility to fetch filter :class:`ICourseCatalogEntry` objects.
    """

    def get_tagged_entries(self, tag):
        """
        Return the set of tagged entries for the given tag.
        """
        tagged_courses = get_courses_for_tag(tag)
        tagged_entries = {
            ICourseCatalogEntry(x, None) for x in tagged_courses
        }
        tagged_entries.discard(None)
        return tagged_entries

    def include_entry(self, entry, filter_str):
        """
        Check if a given entry is included in the given filter.
        """
        filter_str = filter_str.lower()
        result =   (entry.title and filter_str in entry.title.lower()) \
                or (entry.ProviderUniqueID and filter_str in entry.ProviderUniqueID.lower()) \
                or (entry.tags and filter_str in set(x.lower() for x in entry.tags))
        return result

    def _include_entry(self, entry, filter_str, tagged_entries):
        result =   (entry.title and filter_str in entry.title.lower()) \
                or (entry.ProviderUniqueID and filter_str in entry.ProviderUniqueID.lower()) \
                or entry in tagged_entries
        return result

    def filter_entries(self, entries, filter_strs, selector=lambda x: x, union=True):
        """
        Returns a filtered sequence of included :class:`ICourseCatalogEntry`
        matches the given filter str(s). `entry` may be a single instance
        or a sequence.

        If multiple filters are given, we will use the given set operator,
        defaulting to union.

        An optional selector can be given here in order to efficiently
        parse a collection/dict/iter only once when filtering.
        """
        if isinstance(entries, ICourseCatalogEntry):
            entries = (entries,)
        if filter_strs and len(filter_strs) == 1:
            # Special case the single filter - since this is used by UI
            filter_str = filter_strs[0]
            filter_str = filter_str.lower()
            tagged_entries = self.get_tagged_entries(filter_str)
            entries = set(x for x in entries
                          if self._include_entry(selector(x), filter_str, tagged_entries))
        elif filter_strs:
            rs = []
            # Go ahead and get a list in case they gave us an iterator
            all_entries = list(entries)
            for filter_str in filter_strs:
                filter_str = filter_str.lower()
                tagged_entries = self.get_tagged_entries(filter_str)
                entries = set(x for x in all_entries
                              if self._include_entry(selector(x), filter_str, tagged_entries))
                rs.append(entries)
            operator = set.union if union else set.intersection
            entries = reduce(operator, rs)
        return entries

    def _query_index_fields(self, filter_str, sites):
        """
        Query our index fields for any hits on the list of filter_strs.
        """
        rs = []
        courses_catalog = get_courses_catalog()
        for func in (get_entry_intids_for_puid,
                     get_entry_intids_for_tag,
                     get_entry_intids_for_title):
            rs.append(func(filter_str, sites=sites))
        __traceback_info__ = rs
        return reduce(courses_catalog.family.IF.union, rs)

    def get_entry_intids_for_filters(self, filter_strs, union=True):
        """
        For a set of filter strs, filter our course catalog, returning a set of appropriate
        intids.
        """
        sites = get_sites_4_index()
        courses_catalog = get_courses_catalog()
        if union:
            operator = courses_catalog.family.IF.union
        else:
            operator = courses_catalog.family.IF.intersection
        if isinstance(filter_strs, string_types):
            filter_strs = (filter_strs,)
        rs = []
        for filter_str in filter_strs:
            filter_rs = self._query_index_fields(filter_str, sites)
            rs.append(filter_rs)
        if len(rs) == 1:
            result = rs[0]
        else:
            result = reduce(operator, rs)
        return result

    def get_current_entry_intids(self, entry_intids=None):
        """
        Return catalog entries started *before* now and not yet ended - by catalog dates.
        """
        catalog = get_courses_catalog()
        if entry_intids is None:
            # Not given - get the known universe of entry_intids
            # The caller will be responsible getting the narrow
            # set of intids (by site perhaps) they want.
            entry_idx = catalog[IX_ENTRY_TO_COURSE_INTID]
            entry_intids = entry_idx.ids()
        now = datetime.utcnow()
        # This logic is reversed. We'll get the universe of entry intids with
        # start dates *after* now unioned with universe of entry intids with
        # end dates *before* now. All entry intids *not* in this set will be
        # considered for return, which will include entries without any start or end dates.
        exclude_set = self.get_entry_intids_by_dates(start_not_before=now,
                                                     end_not_after=now)
        return catalog.family.IF.difference(entry_intids, exclude_set)

    def get_entry_intids_by_dates(self, union=True,
                                  start_not_before=None, start_not_after=None,
                                  end_not_before=None, end_not_after=None):
        """
        Return catalog entries started *before* not_after and *after* the not_before
        params.
        """
        catalog = get_courses_catalog()
        start_exclude_set = end_exclude_set = None
        if     start_not_after is not None \
            or start_not_before is not None:
            start_exclude_set = catalog.apply({IX_ENTRY_START_DATE:
                                              {'between': (start_not_before, start_not_after)}})
        if     end_not_before is not None \
            or end_not_after is not None:
            end_exclude_set = catalog.apply({IX_ENTRY_END_DATE:
                                            {'between': (end_not_before, end_not_after)}})

        # XXX: What default operator makes sense here?
        if union:
            operator = catalog.family.IF.union
        else:
            operator = catalog.family.IF.intersection
        return operator(start_exclude_set, end_exclude_set)


def is_catalog_anonymously_accessible():
    """
    Returns whether the current ICourseCatalog or any parent ICourseCatalog
    is anonymously_accessible. If any catalog is anonymously_accessible, we
    return True.
    """
    catalog_folder = component.getUtility(ICourseCatalog)
    while catalog_folder is not None:
        if catalog_folder.anonymously_accessible:
            return True
        catalog_folder = queryNextUtility(catalog_folder, ICourseCatalog)
    return False


import zope.deferredimport
zope.deferredimport.initialize()
zope.deferredimport.deprecatedFrom(
    "moved to nti.contenttypes.courses.common",
    "nti.contenttypes.courses.common",
    "get_course_packages",
    "get_course_content_packages")

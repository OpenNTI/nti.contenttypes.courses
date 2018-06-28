#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=no-name-in-module,no-member,too-many-function-args,redefined-outer-name

from six import string_types

from itertools import chain

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from zope.component.interfaces import ComponentLookupError

from zope.container.contained import Contained

from zope.intid.interfaces import IIntIds

from zope.location import LocationIterator

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from ZODB.POSException import POSError

from nti.base.mixins import CreatedAndModifiedTimeMixin

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IEditableContentPackage

from nti.contenttypes.courses.common import get_course_site
from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.index import IX_TAGS
from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import IX_COURSE
from nti.contenttypes.courses.index import IX_PACKAGES
from nti.contenttypes.courses.index import IX_USERNAME
from nti.contenttypes.courses.index import IX_IMPORT_HASH
from nti.contenttypes.courses.index import IX_CONTENT_UNIT

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

from nti.dataserver.authorization import is_admin_or_site_admin
from nti.dataserver.authorization import role_for_providers_content

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IMutableGroupMember

from nti.dataserver.users.users import User

from nti.ntiids.ntiids import get_parts

from nti.site.hostpolicy import get_host_site

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


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
        return tuple(course.SubInstances.values())
    return ()


def get_course_hierarchy(context):
    result = []
    parent = get_parent_course(context)
    if parent is not None:
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
        record = enrollments.get_enrollment_for_principal(user)
        if record is not None and record.Scope == ES_PUBLIC:
            return True
    return False


def get_enrollment_in_hierarchy(course, user):
    if user is None:
        return None
    for instance in get_course_hierarchy(course):
        enrollments = ICourseEnrollments(instance)
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
        enrollments = ICourseEnrollments(instance)
        enrollment = enrollments.get_enrollment_for_principal(user)
        if enrollment is not None:
            enrollment_manager = ICourseEnrollmentManager(instance)
            enrollment_manager.drop(user)
            entry = ICourseCatalogEntry(instance, None)
            logger.warn("User %s dropped from course '%s' open enrollment",
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
            or ICourseInstance.providedBy(obj):
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


def get_instructed_courses(user, **kwargs):
    """
    Returns an iterable containing all the courses
    in which this user is an instructor
    """
    return get_courses_for_scope(user,
                                 scopes=(INSTRUCTOR,),
                                 **kwargs)


def get_instructed_and_edited_courses(user, **kwargs):
    """
    Returns an iterable containing all the courses
    in which this user is either an instructor
    or an editor.
    """
    return get_courses_for_scope(user,
                                 scopes=(INSTRUCTOR, EDITOR),
                                 **kwargs)


def get_instructors_in_roles(roles, setting=Allow):
    """
    return the instructor principal ids for the specified roles with
    the specified setting
    """
    result = set()
    instructors = chain(roles.getPrincipalsForRole(RID_TA) or (),
                        roles.getPrincipalsForRole(RID_INSTRUCTOR) or ())
    for principal, stored in instructors:
        if stored == setting:
            pid = getattr(principal, 'id', str(principal))
            try:
                user = User.get_user(pid)
            except (LookupError, TypeError):
                # lookuperror if we're not in a ds context,
                result.add(pid)
            else:
                if user is not None:
                    result.add(pid)
    return result


def get_course_editors(context, permission=Allow):
    """
    return the principals for the specified course with the specified setting
    """
    result = []
    course = ICourseInstance(context, None)
    role_manager = IPrincipalRoleManager(course, None)
    if role_manager is not None:
        for prin, setting in role_manager.getPrincipalsForRole(RID_CONTENT_EDITOR):
            if setting is permission:
                try:
                    user = User.get_user(prin)
                    principal = IPrincipal(user, None)
                except (LookupError, TypeError):
                    # lookuperror if we're not in a ds context,
                    pass
                else:
                    if principal is not None:
                        result.append(principal)
    return result


def get_course_instructors(context, setting=Allow):
    """
    return the instructor principal ids for the specified course with
    the specified setting
    """
    course = ICourseInstance(context, None)
    roles = IPrincipalRoleMap(course, None)
    result = get_instructors_in_roles(roles, setting) if roles else ()
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
        site = get_host_site(site) if site else None
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


def remove_principal_from_course_content_roles(principal, course, packages=None, unenroll=False):
    """
    Remove the principal from the given course roles (and optional packages).
    We must verify the principal does not have access to this content
    outside of the given course.
    """
    if get_principal(principal) is None:
        return

    if not packages:
        packages = get_course_packages(course)

    courses_to_exclude = (course,) if unenroll else ()

    # Get the minimal set of packages to remove roles for.
    allowed_packages = _get_principal_visible_packages(principal,
                                                       courses_to_exclude=courses_to_exclude)
    to_remove = set(packages) - allowed_packages

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
            x for x in main_course.SubInstances.values() if x is not course
        )

    principal = get_principal(principal)
    if principal is not None:
        for other in potential_other_courses:
            enrollments = ICourseEnrollments(other)
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
        if ICourseSubInstance.providedBy(course):
            parent_course = get_parent_course(course)
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
        logger.warn("Unable to get path for %r, missing parents: %r",
                    context, parents)
        return None
    result = u'/'.join(parents) if parents else None
    return result


def get_courses_for_tag(tag, sites=(), intids=None):
    """
    Given a tag, get all courses with that tag.
    """
    courses = set()
    catalog = get_courses_catalog()
    query = {IX_TAGS: {'any_of': (tag,)}}
    sites = get_sites_4_index(sites)
    if sites:
        query[IX_SITE] = {'any_of': sites}
    intids = component.getUtility(IIntIds) if intids is None else intids
    for uid in catalog.apply(query) or ():
        # Only want catalog entries from index
        obj = intids.queryObject(uid)
        if ICourseCatalogEntry.providedBy(obj):
            course = ICourseInstance(obj, None)
            courses.add(course)
    courses.discard(None)
    result = set()
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


def get_course_tags(filter_str=None, filter_hidden=True):
    """
    Get all course tags. Optionally filtering by the given `filter_str` param
    and by default, removing all hidden tags.
    """
    # NOTE: do we want cardinality or any sort order here?
    catalog = get_courses_catalog()
    tag_index = catalog[IX_TAGS]
    # These will be all in lower case
    tags = set(tag_index.words() or ())
    if filter_hidden:
        tags = filter_hidden_tags(tags)
    if filter_str:
        filter_str = filter_str.lower()
        tags = [x for x in tags if filter_str in x]
    return tags


def get_context_enrollment_records(user, requesting_user):
    """
    For a requesting_user, fetch all relevant enrollment records.
    """
    enrollments = get_enrollments(user)
    if is_admin_or_site_admin(requesting_user) or user == requesting_user:
        # Admins get everything
        result = enrollments
    else:
        # Instructors get enrollment records for the courses they teach.
        result = []
        enrolled_courses_to_records = {x.CourseInstance:x for x in enrollments}
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

    def _include_entry(self, entry, filter_str, tagged_entries):
        result =   (entry.title and filter_str in entry.title.lower()) \
                or (entry.description and filter_str in entry.description.lower()) \
                or (entry.ProviderUniqueID and filter_str in entry.ProviderUniqueID.lower()) \
                or entry in tagged_entries
        return result

    def filter_entries(self, entries, filter_str):
        """
        Returns a filtered sequence of included :class:`ICourseCatalogEntry`
        matches the given filter str. `entry` may be a single instance
        or a sequence. The given order is maintained.
        """
        if isinstance(entries, ICourseCatalogEntry):
            entries = (entries,)
        entries = entries or ()
        if filter_str:
            tagged_entries = self.get_tagged_entries(filter_str)
            entries = [x for x in entries
                       if self._include_entry(x, filter_str, tagged_entries)]
        return entries


import zope.deferredimport
zope.deferredimport.initialize()
zope.deferredimport.deprecatedFrom(
    "moved to nti.contenttypes.courses.common",
    "nti.contenttypes.courses.common",
    "get_course_packages",
    "get_course_content_packages")

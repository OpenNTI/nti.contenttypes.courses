#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sharing support for courses.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# Despite the comments in interfaces.py, right now
# we still stick to a fairly basic Community-derived
# object for sharing purposes. This is largely for compatibility
# and will change.

from itertools import chain

from zope import component
from zope import interface

from zope.cachedescriptors.property import cachedIn

from zope.intid.interfaces import IIntIdAddedEvent
from zope.intid.interfaces import IIntIdRemovedEvent

from zope.lifecycleevent import IObjectMovedEvent
from zope.lifecycleevent import IObjectModifiedEvent

from zope.security.interfaces import IPrincipal

from nti.base._compat import text_

from nti.containers.containers import CheckingLastModifiedBTreeContainer

from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseBundleUpdatedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScopes
from nti.contenttypes.courses.interfaces import ICourseInstanceImportedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import get_principal
from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import deny_access_to_course
from nti.contenttypes.courses.utils import get_course_instructors
from nti.contenttypes.courses.utils import grant_access_to_course
from nti.contenttypes.courses.utils import adjust_scope_membership
from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import add_principal_to_course_content_roles
from nti.contenttypes.courses.utils import remove_principal_from_course_content_roles

from nti.dataserver.authorization import _CommunityGroup

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IUseNTIIDAsExternalUsername

from nti.dataserver.users.communities import Community

from nti.dataserver.users.users import User

from nti.intid.wref import ArbitraryOrderableWeakRef

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseInstanceSharingScope)
class CourseInstanceSharingScope(Community):
    """
    A non-global sharing scope for a course instance.
    """

    # does the UI need this? (Yes, at least the ipad does)
    __external_class_name__ = 'Community'
    __external_can_create__ = False

    mime_type = mimeType = 'application/vnd.nextthought.courses.courseinstancesharingscope'

    # Override things related to ntiids.
    # These don't have global names, so they must be referenced
    # by OID
    NTIID_TYPE = TYPE_OID
    NTIID = cachedIn('_v_ntiid')(to_external_ntiid_oid)

    # Likewise, externalization sometimes wants to spit out unicode(creator),
    # so we need to override that
    def __unicode__(self):
        ntiid = self.NTIID
        if ntiid is not None:
            return ntiid
        del self._v_ntiid
        # Sigh, probably in testing, we don't have an OID
        # or intid yet.
        return text_(str(self))

    # We want, essentially, identity equality:
    # nothing is equal to this because nothing can be contained
    # in the same container as this

    def __eq__(self, other):
        if self is other:
            return True
        try:
            return self.NTIID == other.NTIID
        except AttributeError:
            return NotImplemented

    def __lt__(self, other):
        try:
            return self.NTIID < other.NTIID
        except AttributeError:
            return NotImplemented


# The scopes are a type of entity, but they aren't globally
# named or resolvable by username, so we need to use a better
# weak ref. Plus, there are parts of the code that expect
# IWeakRef to entity to have a username...
class _CourseInstanceSharingScopeWeakRef(ArbitraryOrderableWeakRef):

    @property
    def username(self):
        o = self()
        if o is not None:
            return o.NTIID


# Similarly for acting as principals


@interface.implementer(IUseNTIIDAsExternalUsername)
class _CourseInstanceSharingScopePrincipal(_CommunityGroup):

    def __init__(self, context):
        _CommunityGroup.__init__(self, context)
        # Overwrite id, which defaults to username, with ntiid
        self.id = context.NTIID
        self.NTIID = self.id  # also externalize this way


@interface.implementer(ICourseInstanceSharingScopes)
class CourseInstanceSharingScopes(CheckingLastModifiedBTreeContainer):
    """
    Container for a course's sharing scopes.
    """

    __external_can_create__ = False

    mime_type = mimeType = 'application/vnd.nextthought.courses.courseinstancesharingscopes'

    def _vocabulary(self):
        # Could/should also use the vocabulary registry
        # and dispatch to adapters based on context
        return ENROLLMENT_SCOPE_VOCABULARY

    def __setitem__(self, key, value):
        if key not in self._vocabulary():
            raise KeyError("Unsupported scope kind", key)
        super(CourseInstanceSharingScopes, self).__setitem__(key, value)

    def initScopes(self):
        """
        Make sure we have all the scopes specified by the vocabulary.
        """
        for key in self._vocabulary():
            key = key.token
            if key not in self:
                self[key] = self._create_scope(key)

    def getAllScopesImpliedbyScope(self, scope_name):
        self.initScopes()
        # work with the global superset of terms, but only
        # return things in our local vocabulary
        term = ENROLLMENT_SCOPE_VOCABULARY.getTerm(scope_name)
        names = (scope_name,) + term.implies
        for name in names:
            try:
                scope = self[name]
                yield scope
            except KeyError:
                pass

    def _create_scope(self, name):
        return CourseInstanceSharingScope(name)


class CourseSubInstanceSharingScopes(CourseInstanceSharingScopes):
    """
    The scopes created for a section/sub-instance, which
    handles the implication of joining the parent course scopes.
    """

    __external_class_name__ = 'CourseInstanceSharingScopes'
    __external_can_create__ = False

    def getAllScopesImpliedbyScope(self, scope_name):
        # All of my scopes...
        for i in CourseInstanceSharingScopes.getAllScopesImpliedbyScope(self, scope_name):
            yield i

        # Plus all of the scopes of my parent course instance
        try:
            # me/subinstance/subinstances/course
            parent_course = self.__parent__.__parent__.__parent__
        except AttributeError:
            pass
        else:
            if parent_course is not None:
                scopes = parent_course.SharingScopes.getAllScopesImpliedbyScope(scope_name)
                for i in scopes:
                    yield i


@component.adapter(ICourseInstanceEnrollmentRecord, IIntIdAddedEvent)
def on_enroll_record_scope_membership(record, unused_event, course=None):
    """
    When you enroll in a course, record your membership in the
    proper scopes, including content access.
    """
    course = course or record.CourseInstance
    grant_access_to_course(record.Principal, course, record.Scope)


# We may have intid-weak references to these things,
# so we need to catch them on the IntIdRemoved event
# for dependable ordering
@component.adapter(ICourseInstanceEnrollmentRecord, IIntIdRemovedEvent)
def on_drop_exit_scope_membership(record, unused_event, course=None):
    """
    When you drop a course, leave the scopes you were in, including
    content access.
    """
    course = course or record.CourseInstance
    deny_access_to_course(record.Principal, course, record.Scope)


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectModifiedEvent)
def on_modified_update_scope_membership(record, unused_event):
    """
    When your enrollment record is modified, update the scopes
    you should be in.
    """
    # It would be nice if we could guarantee that
    # the event had its descriptions attribute filled out
    # so we could be sure it was the Scope that got modified,
    # but we can't

    # Try hard to avoid firing events for scopes we don't actually
    # need to exit or add
    principal = get_principal(record.Principal)
    if principal is None:
        return
    sharing_scopes = record.CourseInstance.SharingScopes
    scopes_i_should_be_in = sharing_scopes.getAllScopesImpliedbyScope(record.Scope)
    scopes_i_should_be_in = list(scopes_i_should_be_in)

    drop_from = []
    currently_in = []
    for scope in sharing_scopes.values():
        if principal in scope:
            if scope in scopes_i_should_be_in:
                # A keeper!
                currently_in.append(scope)
            else:
                drop_from.append(scope)

    # First, the drops
    course = record.CourseInstance
    adjust_scope_membership(principal, record.Scope, course,
                            'record_no_longer_dynamic_member',
                            'stop_following',
                            relevant_scopes=drop_from)

    # Now any adds
    adjust_scope_membership(principal, record.Scope, course,
                            'record_dynamic_membership',
                            'follow',
                            currently_in=currently_in,
                            relevant_scopes=scopes_i_should_be_in)


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectMovedEvent)
def on_moved_between_courses_update_scope_membership(record, event):
    """
    We rely on the CourseInstance being in the lineage of the record
    so that we can find the instance that was \"dropped\" by traversing
    through the old parents.
    """

    # This gets called when we are added or removed, because those
    # are both kinds of Moved events. But we only want this for a true
    # move
    if event.oldParent is None or event.newParent is None:
        return

    old_course = find_interface(event.oldParent, ICourseInstance)
    new_course = find_interface(event.newParent, ICourseInstance)

    assert new_course is record.CourseInstance

    on_drop_exit_scope_membership(record, event, old_course)
    on_enroll_record_scope_membership(record, event, new_course)


def update_package_permissions(course, added=None, removed=None):
    """
    Update the package permissions for the enrollees, instructors
    and editors of this course if packages have been added/removed.
    This should be idempotent.
    """
    if not added and not removed:
        # Nothing to do
        return
    courses = [course]
    subinstances = get_course_subinstances(course)
    courses.extend(subinstances)

    for course in courses:
        enrollments = ICourseEnrollments(course)
        entry = ICourseCatalogEntry(course)
        logger.info('Updating package permissions for course (%s)', entry.ntiid)
        # pylint: disable=too-many-function-args
        for principal in chain(enrollments.iter_principals(),
                               get_course_instructors(course),
                               get_course_editors(course)):
            if IPrincipal.providedBy(principal):
                principal = principal.id
            if not IUser.providedBy(principal):
                principal = User.get_user(principal)
            if added:
                add_principal_to_course_content_roles(principal,
                                                      course,
                                                      added)

            if removed:
                remove_principal_from_course_content_roles(principal,
                                                           course,
                                                           packages=removed)


@component.adapter(ICourseInstance, ICourseBundleUpdatedEvent)
def _course_bundle_updated(course, event):
    update_package_permissions(course, event.added_packages,
                               event.removed_packages)


@component.adapter(ICourseInstance, ICourseInstanceImportedEvent)
def on_course_instance_imported(course, unused_event):
    enrollments = ICourseEnrollments(course)
    # pylint: disable=too-many-function-args
    for principal in chain(enrollments.iter_principals(),
                           get_course_instructors(course),
                           get_course_editors(course)):
        if IPrincipal.providedBy(principal):
            principal = principal.id
        if not IUser.providedBy(principal):
            principal = User.get_user(principal)
        add_principal_to_course_content_roles(principal, course)


def get_default_sharing_scope(context):
    """
    Returns the configured default scope for the context.
    """
    course = ICourseInstance(context)
    vendor_info = ICourseInstanceVendorInfo(course, {})
    result = None
    try:
        result = vendor_info['NTI']['DefaultSharingScope']
    except (TypeError, KeyError):
        pass
    else:
        # Could have ntiid or special string
        if is_valid_ntiid_string(result):
            result = find_object_with_ntiid(result)
        else:
            # Ex: Parent/Public or Public
            parts = result.split('/')
            scope = parts[0]
            if len(parts) > 1:
                # We reference a scope in our parent.
                scope = parts[1]
                assert ICourseSubInstance.providedBy(context), \
                       "DefaultSharingScope referencing parent of top-level course."
                # Is this correct, or only correct for Public?
                course = context.__parent__.__parent__
            result = course.SharingScopes[scope]
    return result

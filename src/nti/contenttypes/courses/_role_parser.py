#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reads the instructor role grants and synchronizes them.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.intid.interfaces import IIntIds

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.role import checkRole

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from zope.securitypolicy.securitymap import PersistentSecurityMap

from ZODB.interfaces import IConnection

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.contenttypes.courses.sharing import add_principal_to_course_content_roles
from nti.contenttypes.courses.sharing import remove_principal_from_course_content_roles

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User


def _populate_roles_from_json(course, manager, json):
    """
    A json dict that looks like::

            {
                'role_id':
                     {
                      'allow': ['p1', 'p2'],
                       'deny':  ['p3', 'p4']
                     },
             ... }

    """
    for role_id, role_values in json.items():
        checkRole(course, role_id)
        allows = role_values.get('allow', None)
        for principal_id in allows or ():
            manager.assignRoleToPrincipal(role_id, principal_id)
        denies = role_values.get('deny', None)
        for principal_id in denies or ():
            manager.removeRoleFromPrincipal(role_id, principal_id)


def reset_roles_missing_key(course):
    role_manager = IPrincipalRoleManager(course)
    # We totally cheat here and clear the role manager.
    # this is much easier than trying to actually sync it
    if isinstance(role_manager.map, PersistentSecurityMap):
        role_manager.map._byrow.clear()
        role_manager.map._bycol.clear()
        role_manager.map._p_changed = True


def _check_scopes(course):
    # CS: In alpha we have seen scopes missing its intids
    # Let's try to give it an intid
    intids = component.queryUtility(IIntIds)
    if intids is None:
        return
    for scope in course.SharingScopes.values():
        uid = intids.queryId(scope)
        obj = intids.queryObject(uid) if uid is not None else None
        if uid is None or obj != scope:
            if IConnection(scope, None) is None:
                IConnection(course).add(scope)

            if uid is not None and obj is None:
                logger.warn("Reregistering scope %s in course %r with intid facility",
                            scope, course)
                intids.forceRegister(uid, scope)
            else:
                logger.warn("A new intid will be given to scope %s in course %r",
                            scope, course)
                if hasattr(scope, intids.attribute):
                    delattr(scope, intids.attribute)
                intids.register(scope)


def _unenroll_instructor(instructor, course):
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


def fill_roles_from_json(course, json):
    _check_scopes(course)

    role_manager = IPrincipalRoleManager(course)
    reset_roles_missing_key(role_manager)

    _populate_roles_from_json(course, role_manager, json)

    # We must update the instructor list too, it's still used internally
    # in a few places...plus it's how we know who to remove from the scopes

    # Any instructors that were present but aren't present
    # anymore need to lose access to the sharing scopes
    orig_instructors = course.instructors
    course.instructors = ()

    # For any of these that exist as users, we need to make sure they
    # are in the appropriate sharing scopes too...
    # NOTE: We only take care of addition, we do not handle removal,
    # (that could be done with some extra work)
    for role_id, pid, setting in role_manager.getPrincipalsAndRoles():
        is_instructor = bool(role_id in (RID_INSTRUCTOR, RID_TA))
        if     setting is not Allow \
            or (not is_instructor and not role_id == RID_CONTENT_EDITOR):
            continue

        try:
            user = User.get_user(pid)
            if is_instructor:
                course.instructors += (IPrincipal(user),)
                _unenroll_instructor(user, course)
        except (LookupError, TypeError):
            # lookuperror if we're not in a ds context,
            # TypeError if no named user was found and none was returned
            # and the adaptation failed
            pass
        else:
            # XXX: The addition and removal here are eerily similar
            # to what enrollment does and they've gotten out of sync
            # in the past.
            add_principal_to_course_content_roles(user, course)
            if not is_instructor:
                continue
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

    for orig_instructor in orig_instructors:
        if orig_instructor not in course.instructors:
            user = IUser(orig_instructor)
            # by definition here we have an IPrincipal that *came* from an IUser
            # and has a hard reference to it, and so can become an IUser again
            remove_principal_from_course_content_roles(user, course)
            for scope in course.SharingScopes.values():
                user.record_no_longer_dynamic_member(scope)
                user.stop_following(scope)

            # And remove access to the parent public scope.
            if ICourseSubInstance.providedBy(course):
                parent_course = get_parent_course(course)
                public_scope = parent_course.SharingScopes[ES_PUBLIC]
                user.record_no_longer_dynamic_member(public_scope)
                user.stop_following(public_scope)

    return True


def fill_roles_from_key(course, key):
    __traceback_info__ = key, course
    role_last_mod = getattr(course, '__principalRoleslastModified__', 0)
    if key.lastModified <= role_last_mod:
        # JAM: XXX: We had some environments that got set up
        # before instructors were properly added to content roles;
        # rather than force environments to remove the role files and
        # sync, then put them back and sync again, I'm temporarily
        # setting roles each time we get here. It's an idempotent process,
        # though, so we won't be churning the database.
        for instructor in course.instructors:
            user = IUser(instructor)
            add_principal_to_course_content_roles(user, course)
        return False

    logger.info('Syncing course roles for key (%s)', key)
    json = key.readContentsAsYaml()
    result = fill_roles_from_json(course, json)
    course.__principalRoleslastModified__ = key.lastModified
    return result

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reads the instructor role grants and synchronizes them.

.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.intid.interfaces import IIntIds

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.role import checkRole

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from ZODB.interfaces import IConnection

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.utils import grant_instructor_access_to_course

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


def fill_roles_from_json(course, json):
    """
    Give our roles permissions on the course and course objects. We will only
    allow granting of new access here; removal of access must occur through
    the API.
    """
    _check_scopes(course)
    role_manager = IPrincipalRoleManager(course)
    _populate_roles_from_json(course, role_manager, json)
    # We must update the instructor list too, it's still used internally
    # in a few places...plus it's how we know who to remove from the scopes
    for role_id, pid, setting in role_manager.getPrincipalsAndRoles():
        is_instructor = bool(role_id in (RID_INSTRUCTOR, RID_TA))
        if     setting is not Allow \
            or (not is_instructor and not role_id == RID_CONTENT_EDITOR):
            continue

        try:
            user = User.get_user(pid)
            user_prin = IPrincipal(user)
            if is_instructor and user_prin not in course.instructors:
                course.instructors += (user_prin,)
        except (LookupError, TypeError):
            # lookuperror if we're not in a ds context,
            # TypeError if no named user was found and none was returned
            # and the adaptation failed
            pass
        else:
            grant_instructor_access_to_course(user, course)
    return True


def fill_roles_from_key(course, key):
    __traceback_info__ = key, course
    role_last_mod = getattr(course, '__principalRoleslastModified__', 0)
    if key.lastModified <= role_last_mod:
        return False

    logger.info('Syncing course roles for key (%s)', key)
    json = key.readContentsAsYaml()
    result = fill_roles_from_json(course, json)
    course.__principalRoleslastModified__ = key.lastModified
    return result

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from itertools import chain

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_TA

from nti.dataserver.users.users import User

from nti.site.interfaces import IHostPolicyFolder

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import IPrincipalRoleManager

logger = __import__('logging').getLogger(__name__)


def get_course_packages(context):
    course = ICourseInstance(context, None)
    if course is not None:
        try:
            packs = course.ContentPackageBundle.ContentPackages or ()
        except AttributeError:
            try:
                packs = (course.legacy_content_package,)
            except AttributeError:
                packs = ()
        return packs or ()
    return ()
get_course_content_packages = get_course_packages


def get_course_content_units(context):
    content_units = []

    def _recur(content_unit, accum):
        accum.append(content_unit)
        for child in content_unit.children or ():
            _recur(child, accum)

    for packag in get_course_packages(context):
        _recur(packag, content_units)
    return content_units


def get_course_site_name(context):
    folder = IHostPolicyFolder(ICourseInstance(context, None), None)
    return folder.__name__ if folder is not None else None
get_course_site = get_course_site_name


def get_course_site_registry(context):
    course = ICourseInstance(context, None)
    folder = IHostPolicyFolder(course, None)
    # pylint: disable=too-many-function-args
    return folder.getSiteManager() if folder is not None else None


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


def get_course_instructors(context, setting=Allow):
    """
    return the instructor principal ids for the specified course with
    the specified setting
    """
    course = ICourseInstance(context, None)
    roles = IPrincipalRoleMap(course, None)
    result = get_instructors_in_roles(roles, setting) if roles else ()
    return result


def get_course_editors(context, permission=Allow):
    """
    return the principals for the specified course with the specified setting
    """
    result = []
    course = ICourseInstance(context, None)
    role_manager = IPrincipalRoleManager(course, None)
    if role_manager is not None:
        # pylint: disable=too-many-function-args
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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid.interfaces import IIntIds

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR

from nti.contenttypes.courses.interfaces import ICourseInstanceAdministrativeRole
from nti.contenttypes.courses.interfaces import IPrincipalAdministrativeRoleCatalog

from nti.contenttypes.courses.utils import AbstractInstanceWrapper
from nti.contenttypes.courses.utils import get_all_site_course_intids
from nti.contenttypes.courses.utils import get_site_course_admin_intids_for_user

from nti.dataserver.authorization import is_admin
from nti.dataserver.authorization import is_site_admin
from nti.dataserver.authorization import is_content_admin

from nti.dataserver.interfaces import IUser

from nti.schema.fieldproperty import createDirectFieldProperties

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseInstanceAdministrativeRole)
class CourseInstanceAdministrativeRole(AbstractInstanceWrapper):
    createDirectFieldProperties(ICourseInstanceAdministrativeRole,
                                # Be flexible about what this is,
                                # the
                                # LegacyCommunityInstance
                                # doesn't fully
                                # comply
                                omit=('CourseInstance',))

    # legacy
    mime_type = mimeType = "application/vnd.nextthought.courseware.courseinstanceadministrativerole"

    def __init__(self, CourseInstance=None, RoleName=None):
        self.CourseInstance = CourseInstance
        self.RoleName = RoleName
        AbstractInstanceWrapper.__init__(self, CourseInstance)


def get_course_admin_role(course, user, is_admin=False):  # pylint: disable=redefined-outer-name
    """
    Given a user and course, return the `ICourseInstanceAdministrativeRole` that
    maps to that user's administrative capability.
    """
    role = u'editor'
    if not is_admin:
        user = IPrincipal(user)
        roles = IPrincipalRoleMap(course)
        if roles.getSetting(RID_INSTRUCTOR, user.id) is Allow:
            role = u'instructor'
        elif roles.getSetting(RID_TA, user.id) is Allow:
            role = u'teaching assistant'
    return CourseInstanceAdministrativeRole(RoleName=role,
                                            CourseInstance=course)


@component.adapter(IUser)
@interface.implementer(IPrincipalAdministrativeRoleCatalog)
class _DefaultPrincipalAdministrativeRoleCatalog(object):
    """
    This catalog returns all courses the user is in the instructors list,
    or all courses if the user is an admin, site admin, or global content
    admin.
    """

    def __init__(self, user):
        self.user = user

    @Lazy
    def _is_admin(self):
        return is_admin(self.user)

    @Lazy
    def _is_site_admin(self):
        return is_site_admin(self.user)

    @Lazy
    def _is_content_admin(self):
        return is_content_admin(self.user)

    @Lazy
    def _is_global_admin(self):
        return self._is_admin \
            or self._is_content_admin

    @Lazy
    def _course_intids(self):
        # We do not filter based on enrollment or anything else.
        # This will probably move to its own workspace eventually.
        if self._is_global_admin:
            result = get_all_site_course_intids()
        else:
            # Site admins can admin in any course in any of their sites.
            # This also adds instructed and edited courses.
            result = get_site_course_admin_intids_for_user(self.user)
        return result

    def get_course_intids(self):
        return self._course_intids

    def iter_admin_roles_for_intids(self, course_intids):
        """
        Reifies and returns admin roles for the given intids.
        """
        is_admin = self._is_global_admin or self._is_site_admin
        intids = component.getUtility(IIntIds)
        for course_intid in course_intids:
            course = intids.queryObject(course_intid)
            if course is not None:
                admin_role = get_course_admin_role(course,
                                                   self.user,
                                                   is_admin=is_admin)
                yield admin_role

    def iter_administrations(self):
        return self.iter_admin_roles_for_intids(self._course_intids)

    iter_enrollments = iter_administrations  # for convenience

    def count_administrations(self):
        return len(self._course_intids)

    count_enrollments = count_administrations

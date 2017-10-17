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

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IUserAdministeredCourses
from nti.contenttypes.courses.interfaces import ICourseInstanceAdministrativeRole
from nti.contenttypes.courses.interfaces import IPrincipalAdministrativeRoleCatalog

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_instructed_and_edited_courses
from nti.contenttypes.courses.utils import AbstractInstanceWrapper

from nti.dataserver.authorization import is_admin
from nti.dataserver.authorization import is_content_admin

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.interfaces import IUser

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IUserAdministeredCourses)
class IndexAdminCourses(object):

    def iter_admin(self, user):
        results = get_instructed_and_edited_courses(user)
        for result in results:
            if ICourseInstance.providedBy(result):  # extra check
                yield result


@interface.implementer(IUserAdministeredCourses)
class IterableAdminCourses(object):

    def iter_admin(self, user):
        principal = IPrincipal(user)
        catalog = component.getUtility(ICourseCatalog)
        for entry in catalog.iterCatalogEntries():
            instance = ICourseInstance(entry)
            instructors = instance.instructors or ()
            if     principal in instructors \
                or principal in get_course_editors(instance):
                yield instance


@interface.implementer(ICourseInstanceAdministrativeRole)
class CourseInstanceAdministrativeRole(SchemaConfigured,
                                       AbstractInstanceWrapper):
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
        # SchemaConfigured is not cooperative
        SchemaConfigured.__init__(self, RoleName=RoleName)
        AbstractInstanceWrapper.__init__(self, CourseInstance)


def get_course_admin_role(course, user, is_admin=False):
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
    or all courses if the user is a global content admin.
    """

    def __init__(self, user):
        self.user = user

    @Lazy
    def _is_admin(self):
        return is_admin(self.user)

    @Lazy
    def _is_content_admin(self):
        return is_content_admin(self.user)

    def _iter_all_courses(self):
        # We do not filter based on enrollment or anything else.
        # This will probably move to its own workspace eventually.
        catalog = component.queryUtility(ICourseCatalog)
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            if course is not None \
                and not ILegacyCourseInstance.providedBy(course) \
                and (   self._is_admin
                     or has_permission(ACT_CONTENT_EDIT, entry, self.user)):
                yield course

    def _iter_admin_courses(self):
        util = component.getUtility(IUserAdministeredCourses)
        for context in util.iter_admin(self.user):
            yield context

    def _get_course_iterator(self):
        if self._is_admin or self._is_content_admin:
            result = self._iter_all_courses
        else:
            result = self._iter_admin_courses
        return result

    def iter_administrations(self):
        course_iter_func = self._get_course_iterator()
        for course in course_iter_func():
            admin_role = get_course_admin_role(course,
                                               self.user,
                                               is_admin=self._is_admin)
            yield admin_role

    iter_enrollments = iter_administrations  # for convenience

    def count_administrations(self):
        result = tuple(self._iter_admin_courses())
        return len(result)

    count_enrollments = count_administrations

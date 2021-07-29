#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904
from hamcrest import has_item
from hamcrest import is_
from hamcrest import empty
from hamcrest import is_in
from hamcrest import contains
from hamcrest import assert_that

from nti.testing.matchers import validly_provides

import unittest

from zope import interface
from zope.annotation import IAttributeAnnotatable
from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import Unset
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR

from nti.contenttypes.courses.principalrole import CourseInstancePrincipalRoleMap
from nti.contenttypes.courses.principalrole import CourseRolePermissionManager

from nti.contenttypes.courses.utils import get_instructors_in_roles

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class _PhonyPrincipal(object):

    id = None

    def __init__(self, pid):
        self.id = pid


@interface.implementer(IAttributeAnnotatable)
class _PhonyCourse(object):

    instructors = []

    def __init__(self):
        self.instructors = []

    def _add_instructor(self, pid):
        self.instructors.append(_PhonyPrincipal(pid))


class TestCourseInstancePrincipalRoleMap(unittest.TestCase):

    course = None
    rolemap = None

    def setUp(self):
        super(TestCourseInstancePrincipalRoleMap, self).setUp()
        self.course = _PhonyCourse()
        self.rolemap = CourseInstancePrincipalRoleMap(self.course)

    def test_provides(self):
        assert_that(self.rolemap, validly_provides(IPrincipalRoleMap))

    def test_principals_for_role(self):
        # initially empty, no instructors
        assert_that(self.rolemap.getPrincipalsForRole('foo'), is_(empty()))
        assert_that(self.rolemap.getPrincipalsForRole(RID_TA), is_(empty()))
        assert_that(self.rolemap.getPrincipalsForRole(RID_INSTRUCTOR), 
                    is_(empty()))

        self.course._add_instructor('foo')

        assert_that(self.rolemap.getPrincipalsForRole(RID_TA), is_(empty()))
        assert_that(self.rolemap.getPrincipalsForRole(RID_INSTRUCTOR),
                    contains(('foo', Allow)))

        instructors = get_instructors_in_roles(self.rolemap)
        assert_that('foo', is_in(instructors))

    def test_roles_for_principal(self):
        assert_that(self.rolemap.getRolesForPrincipal('foo'), is_(empty()))
        self.course._add_instructor('foo')

        assert_that(self.rolemap.getRolesForPrincipal('foo'),
                    contains((RID_INSTRUCTOR, Allow)))
        assert_that(self.rolemap.getRolesForPrincipal('foo2'), is_(empty()))

    def test_get_setting(self):
        assert_that(self.rolemap.getSetting('bad role', None),
                    is_(Unset))
        assert_that(self.rolemap.getSetting(RID_TA, 'foo'),
                    is_(Unset))

        self.course._add_instructor('foo')

        assert_that(self.rolemap.getSetting(RID_INSTRUCTOR, 'foo'),
                    is_(Allow))
        assert_that(self.rolemap.getSetting(RID_TA, 'foo'),
                    is_(Unset))

    def test_get_all(self):
        assert_that(self.rolemap.getPrincipalsAndRoles(),
                    is_(empty()))

        self.course._add_instructor('foo')

        assert_that(self.rolemap.getPrincipalsAndRoles(),
                    contains((RID_INSTRUCTOR, 'foo', Allow)))


class TestCourseRolePermissionManager(CourseLayerTest):

    course = None
    rolemap = None

    def setUp(self):
        super(TestCourseRolePermissionManager, self).setUp()
        self.course = _PhonyCourse()
        self.rolemap = CourseRolePermissionManager(self.course)

    @WithMockDSTrans
    def test_permissions(self):
        assert_that(self.rolemap.getRolesAndPermissions(),
                    has_item((ACT_READ.id, ROLE_ADMIN.id, Allow)))

        assert_that(self.rolemap.getPermissionsForRole(ROLE_ADMIN.id),
                    has_item((ACT_READ.id, Allow)))

        assert_that(self.rolemap.getRolesForPermission(ACT_READ.id),
                    has_item((ROLE_ADMIN.id, Allow)))

        assert_that(self.rolemap.getSetting(ACT_READ.id, ROLE_ADMIN.id),
                    Allow)

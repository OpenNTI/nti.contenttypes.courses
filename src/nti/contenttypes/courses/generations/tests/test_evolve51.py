#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ
from hamcrest import has_item
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import not_

from zope.securitypolicy.settings import Allow

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.generations.evolve51 import process_course

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseRolePermissionManager
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
from nti.dataserver.tests.mock_dataserver import DataserverLayerTest


class TestEvolve(DataserverLayerTest):

    @WithMockDSTrans
    def test_evolve_no_perm(self):
        course = self._create_course(u'tag:nextthought.com,2011-10:NTI-CourseInfo-IAS_5912')

        # Place in state of course prior to changing CourseRolePermissionManager
        course_role_manager = ICourseRolePermissionManager(course)
        course_role_manager.initialize()
        course_role_manager.unsetPermissionFromRole(ACT_READ.id, ROLE_ADMIN.id)

        # Ensure any other persisted permissions are preserved
        course_role_manager.grantPermissionToRole('foo', 'role:bar')

        roles_and_perms = course_role_manager.getRolesAndPermissions()

        assert_that(roles_and_perms, not_(has_item((ACT_READ.id, ROLE_ADMIN.id, Allow))))

        process_course(course)

        new_roles_and_perms = course_role_manager.getRolesAndPermissions()
        diff = set(new_roles_and_perms) - set(roles_and_perms)
        assert_that(diff, has_length(1))
        assert_that(list(diff)[0], is_((ACT_READ.id, ROLE_ADMIN.id, Allow)))
        assert_that(new_roles_and_perms, has_length(len(roles_and_perms) + 1))
        assert_that(new_roles_and_perms, has_item((ACT_READ.id, ROLE_ADMIN.id, Allow)))
        assert_that(new_roles_and_perms, has_item(('foo', 'role:bar', Allow)))

    @WithMockDSTrans
    def test_evolve_perm(self):
        course = self._create_course(u'tag:nextthought.com,2011-10:NTI-CourseInfo-IAS_5912')

        # Place in state of course prior to changing CourseRolePermissionManager
        course_role_manager = ICourseRolePermissionManager(course)
        course_role_manager.initialize()

        roles_and_perms = course_role_manager.getRolesAndPermissions()

        assert_that(roles_and_perms, has_item((ACT_READ.id, ROLE_ADMIN.id, Allow)))

        process_course(course)

        new_roles_and_perms = course_role_manager.getRolesAndPermissions()
        assert_that(new_roles_and_perms, has_length(len(roles_and_perms)))
        assert_that(new_roles_and_perms, has_item((ACT_READ.id, ROLE_ADMIN.id, Allow)))

    def _create_course(self, ntiid):
        course = ContentCourseInstance()
        conn = mock_dataserver.current_transaction
        conn.add(course)
        entry = ICourseCatalogEntry(course)
        entry.ntiid = ntiid
        return course

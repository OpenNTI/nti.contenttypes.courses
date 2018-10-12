#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that

from zope import interface

from zope.securitypolicy.interfaces import IRolePermissionManager
from zope.securitypolicy.interfaces import Deny

from nti.contenttypes.courses.tests import CourseLayerTest
from nti.contenttypes.courses.forum import CourseInstanceBoard

from nti.contenttypes.courses.interfaces import ICourseInstanceForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from nti.dataserver.contenttypes.forums.interfaces import IDefaultForumBoard
from nti.dataserver.contenttypes.forums.forum import CommunityForum

from nti.dataserver.authorization import ACT_DELETE
from nti.dataserver.authorization import ROLE_SITE_ADMIN

class TestForum(CourseLayerTest):

    def test_course_forum(self):
        board = CourseInstanceBoard()
        forum = CommunityForum()

        assert_that(ICourseInstanceForum.providedBy(forum), is_(False))
        board['foo'] = forum
        assert_that(ICourseInstanceForum.providedBy(forum), is_(True))

    def test_course_board_no_default(self):
        board = CourseInstanceBoard()
        assert_that(IDefaultForumBoard(board, None), is_(None))


class TestPermissions(CourseLayerTest):

    def test_site_admin_no_delete(self):
        board = CourseInstanceBoard()
        forum = CommunityForum()
        board['foo'] = forum

        interface.alsoProvides(forum, ICourseInstanceForCreditScopedForum)

        rpm = IRolePermissionManager(forum)
        can_delete = rpm.getSetting(ACT_DELETE.id, ROLE_SITE_ADMIN.id)

        assert_that(can_delete, is_(Deny))

        

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that

from zope import component
from zope import interface

from nti.contenttypes.courses.tests import CourseLayerTest
from nti.contenttypes.courses.forum import CourseInstanceBoard

from nti.contenttypes.courses.interfaces import ICourseInstanceForum

from nti.dataserver.contenttypes.forums.interfaces import IDefaultForumBoard
from nti.dataserver.contenttypes.forums.forum import CommunityForum

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
    

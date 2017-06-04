#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.model import CourseDiscussion

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.dataserver.tests import mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class TestAdapters(CourseLayerTest):

    @WithMockDSTrans
    def test_course_discussions(self):
        connection = mock_dataserver.current_transaction
        inst = CourseInstance()
        connection.add(inst)

        discussions = ICourseDiscussions(inst, None)
        assert_that(discussions, is_not(none()))
        assert_that(discussions, has_property('__parent__', is_(inst)))

        discussion = CourseDiscussion()
        discussion.id = u'foo'
        discussions[u'foo'] = discussion
        assert_that(discussions, has_entry('foo', is_(discussion)))

        course = ICourseInstance(discussion, None)
        assert_that(course, is_not(none()))
        assert_that(course, is_(inst))

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property

from nti.contenttypes.courses.catalog import CourseCatalogFolder

from nti.contenttypes.courses.courses import CourseInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.model import CourseDiscussion

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.dataserver.tests import mock_dataserver


class TestAdapters(CourseLayerTest):

    @mock_dataserver.WithMockDSTrans
    def test_course_discussions(self):
        connection = mock_dataserver.current_transaction
        
        catalog = CourseCatalogFolder()
        catalog.__name__ = u'Courses'
        connection.add(catalog)

        admin = CourseAdministrativeLevel()
        connection.add(admin)
        catalog['sample'] = admin
    
        inst = CourseInstance()
        connection.add(inst)
        admin['sample'] = inst

        discussions = ICourseDiscussions(inst, None)
        assert_that(discussions, is_not(none()))
        assert_that(discussions, has_property('__parent__', is_(inst)))

        discussion = CourseDiscussion()
        discussion.id = u'foo'
        discussions[u'foo'] = discussion
        assert_that(discussions, has_entry('foo', is_(discussion)))
        assert_that(discussions, has_length(1))

        course = ICourseInstance(discussion, None)
        assert_that(course, is_not(none()))
        assert_that(course, is_(inst))

        del admin['sample']
        assert_that(discussions, has_length(0))

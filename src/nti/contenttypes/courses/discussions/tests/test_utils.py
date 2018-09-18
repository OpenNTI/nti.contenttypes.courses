#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import assert_that

from nti.contenttypes.courses.discussions.model import CourseDiscussion

from nti.contenttypes.courses.discussions.utils import get_discussion_key
from nti.contenttypes.courses.discussions.utils import is_nti_course_bundle
from nti.contenttypes.courses.discussions.utils import get_discussion_mapped_scopes

from nti.contenttypes.courses.tests import CourseLayerTest


class TestUtils(CourseLayerTest):

    def test_course_bundle(self):
        iden = u'nti-course-bundle://Sections/010/Discussions/d0.json'
        discussion = CourseDiscussion()
        discussion.title = u'11:6:Perspectives'
        discussion.scopes = (u'All',)
        discussion.id = iden
        assert_that(is_nti_course_bundle(iden), is_(True))
        assert_that(is_nti_course_bundle(discussion), is_(True))
        assert_that(get_discussion_key(discussion), is_('d0.json'))

    def test_scopes(self):
        discussion = CourseDiscussion()
        discussion.title = u'11:6:Perspectives'
        discussion.scopes = (u'All',)
        discussion.id = u'nti-course-bundle://Sections/010/Discussions/d0.json'
        assert_that(sorted(get_discussion_mapped_scopes(discussion)),
                    is_(['ForCredit', 'Public']))

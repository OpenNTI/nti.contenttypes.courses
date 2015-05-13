#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that

from nti.contenttypes.courses.discussions.model import CourseDiscussion
from nti.contenttypes.courses.discussions.utils import get_discussion_key
from nti.contenttypes.courses.discussions.utils import is_nti_course_bundle
from nti.contenttypes.courses.discussions.utils import get_discussion_mapped_scopes

from nti.contenttypes.courses.tests import CourseLayerTest

class TestUtils(CourseLayerTest):

	def test_course_bundle(self):
		iden = 'nti-course-bundle://Sections/010/Discussions/d0.json'
		discussion = CourseDiscussion()
		discussion.title = '11:6:Perspectives'
		discussion.scopes = (u'All',)
		discussion.id = iden
		assert_that(is_nti_course_bundle(iden), is_(True))
		assert_that(is_nti_course_bundle(discussion), is_(True))
		assert_that(get_discussion_key(discussion), is_('d0.json'))

	def test_scopes(self):
		discussion = CourseDiscussion()
		discussion.title = '11:6:Perspectives'
		discussion.scopes = (u'All',)
		discussion.id = 'nti-course-bundle://Sections/010/Discussions/d0.json'
		assert_that(list(get_discussion_mapped_scopes(discussion)),
					is_([u'ForCredit', u'Public']))

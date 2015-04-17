#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that
from hamcrest import has_entries

from nti.contenttypes.courses.discussions.model import CourseDiscussion
from nti.contenttypes.courses.discussions.utils import get_topics_ntiids

from nti.contenttypes.courses.tests import CourseLayerTest

class TestUtils(CourseLayerTest):

	def test_get_topics_ntiids_ids(self):
		discussion = CourseDiscussion()
		discussion.scopes = (u'All',)
		discussion.id = 'nti-course-bundle://Sections/010/Discussions/d0.json'
		result = get_topics_ntiids(discussion, provider='LSTD_1153')
		assert_that(result, 
					has_entries(
						'Public', u'tag:nextthought.com,2011-10:LSTD_1153-Topic-Open_Sections_010_Discussions_d0_json',
						'Purchased', u'tag:nextthought.com,2011-10:LSTD_1153-Topic-Purchased_Sections_010_Discussions_d0_json',
						'ForCredit', u'tag:nextthought.com,2011-10:LSTD_1153-Topic-ForCredit_Sections_010_Discussions_d0_json',
						'ForCreditDegree', u'tag:nextthought.com,2011-10:LSTD_1153-Topic-ForCreditDegree_Sections_010_Discussions_d0_json',
						'ForCreditNonDegree', u'tag:nextthought.com,2011-10:LSTD_1153-Topic-ForCreditNonDegree_Sections_010_Discussions_d0_json'),
					)

	def test_get_topics_ntiids_title(self):
		discussion = CourseDiscussion()
		discussion.title = '11:6:Perspectives'
		discussion.scopes = (u'All',)
		result = get_topics_ntiids(discussion, provider='LSTD_1153')
		
		assert_that(result, 
					has_entries(
						'Public', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseRoot-Open_Discussions_11_6_Perspectives',
						'Purchased', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseRoot-Purchased_Discussions_11_6_Perspectives',
						'ForCredit', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseRoot-ForCredit_Discussions_11_6_Perspectives',
						'ForCreditDegree', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseRoot-ForCreditDegree_Discussions_11_6_Perspectives',
						'ForCreditNonDegree', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseRoot-ForCreditNonDegree_Discussions_11_6_Perspectives')
					)

	def test_get_topics_ntiids_title_section(self):
		discussion = CourseDiscussion()
		discussion.title = '11:6:Perspectives'
		discussion.scopes = (u'All',)
		result = get_topics_ntiids(discussion, provider='LSTD_1153', is_section=True)
		
		assert_that(result, 
					has_entries(
						'Public', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseSection-Open_Discussions_11_6_Perspectives',
						'Purchased', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseSection-Purchased_Discussions_11_6_Perspectives',
						'ForCredit', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseSection-ForCredit_Discussions_11_6_Perspectives',
						'ForCreditDegree', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseSection-ForCreditDegree_Discussions_11_6_Perspectives',
						'ForCreditNonDegree', u'tag:nextthought.com,2011-10:LSTD_1153-Topic:EnrolledCourseSection-ForCreditNonDegree_Discussions_11_6_Perspectives')
					)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import all_of
from hamcrest import has_key
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property

import fudge

from nti.contenttypes.courses.courses import CourseInstance
from nti.contenttypes.courses.assignment import MappingAssignmentPolicies

from nti.contenttypes.courses.grading import set_grading_policy_for_course

from nti.contenttypes.courses.grading.policies import EqualGroupGrader
from nti.contenttypes.courses.grading.interfaces import IEqualGroupGrader
from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy
from nti.contenttypes.courses.grading.policies import DefaultCourseGradingPolicy

from nti.externalization import internalization
from nti.externalization import externalization

from nti.contenttypes.courses.tests import CourseLayerTest

import nti.dataserver.tests.mock_dataserver as mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.testing.matchers import validly_provides

class TestPolicies(CourseLayerTest):

	def test_equal_grader(self):
		grader = EqualGroupGrader()
		grader.groups = {'exams': 2}
		assert_that( grader, validly_provides(IEqualGroupGrader) )
		
		ext_obj = externalization.toExternalObject(grader)
		assert_that(ext_obj, all_of(has_key('Class'),
									has_entry('Groups', has_entry('exams', 2)),
									has_entry('MimeType', 'application/vnd.nextthought.courses.grading.equalgroupgrader')))
		
		assert_that(internalization.find_factory_for(ext_obj),
					 is_(not_none()))

		internal = internalization.find_factory_for(ext_obj)()
		internalization.update_from_external_object(internal,
													 ext_obj,
													 require_updater=True)
		
		assert_that(internal, has_property('Groups', has_entry('exams', 0.02)))

	def test_validation_equal_grader(self):
		grader = EqualGroupGrader()
		grader.groups = {'exams': 0.2, "homeworks":0.9}
		with self.assertRaises(AssertionError):
			grader.validate() # add more than one
		grader.groups = {'exams': 0.2, "homeworks":0.7}
		with self.assertRaises(AssertionError):
			grader.validate() #
	
	@WithMockDSTrans
	@fudge.patch('nti.contenttypes.courses.grading.policies.get_assignment',
				 'nti.contenttypes.courses.grading.policies.get_assignment_policies')
	def test_course_policy(self, mock_ga, mock_gap):
		connection = mock_dataserver.current_transaction
		course = CourseInstance()
		connection.add(course)

		grader = EqualGroupGrader()
		grader.groups = {'exams': 0.2, "homeworks":0.8}
		policy = DefaultCourseGradingPolicy(Grader=grader)
		assert_that(policy, has_property('Grader', is_(not_none())))
		
		assert_that( policy, validly_provides(ICourseGradingPolicy) )
		set_grading_policy_for_course(course, policy)
		
		assert_that(policy, has_property('course', is_(course)))
		assert_that(grader, has_property('course', is_(course)))
		
		adapted = ICourseGradingPolicy(course, None)
		assert_that(adapted, is_(not_none()))

		ext_obj = externalization.toExternalObject(policy)
		assert_that(ext_obj, all_of(has_key('Class'),
									has_entry('Grader', has_entry('Groups', has_entry('homeworks', 0.8))),
									has_entry('MimeType', 'application/vnd.nextthought.courses.grading.defaultpolicy')))
		
		internal = internalization.find_factory_for(ext_obj)()
		internalization.update_from_external_object(internal,
													ext_obj,
													require_updater=True)
		
		assert_that(internal, has_property('Grader', has_property('Groups', has_entry('homeworks', 0.8))))
		assert_that(internal, has_property('Grader', has_property('Groups', has_entry('exams', 0.2))))
		
		mock_ga.is_callable().with_args().returns(fudge.Fake())
		
		cap = MappingAssignmentPolicies()
		cap['a1'] = {'grader': {'group':'exams'}}
		cap['a2'] = {'grader': {'group':'homeworks'}}
		
		mock_gap.is_callable().with_args().returns(cap)
		policy.validate()

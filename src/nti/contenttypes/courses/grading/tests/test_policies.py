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

from nti.contenttypes.courses.grading.policies import EqualGroupGrader
from nti.contenttypes.courses.grading.interfaces import IEqualGroupGrader

from nti.externalization import internalization
from nti.externalization import externalization

from nti.testing.matchers import validly_provides

from nti.contenttypes.courses.tests import CourseLayerTest

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

	def test_validation(self):
		grader = EqualGroupGrader()
		grader.groups = {'exams': 0.2, "homeworks":0.9}
		with self.assertRaises(AssertionError):
			grader.validate()

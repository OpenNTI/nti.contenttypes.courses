#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904


from hamcrest import assert_that
from hamcrest import is_
from hamcrest import has_property
from hamcrest import has_entry
from hamcrest import not_none
from hamcrest import same_instance

from nti.testing import base
from nti.testing import matchers

from nti.testing.matchers import verifiably_provides

from .. import courses
from .. import interfaces


class TestCourseInstance(base.AbstractTestBase):

	def test_course_implements(self):
		assert_that( courses.CourseInstance(), verifiably_provides(interfaces.ICourseInstance) )

	def test_course_containment(self):
		inst = courses.CourseInstance()
		parent = courses.CourseAdministrativeLevel()
		parent['Course'] = inst
		gp = courses.CourseAdministrativeLevel()
		gp['Child'] = parent
		assert_that( gp, verifiably_provides(interfaces.ICourseAdministrativeLevel) )

	def test_course_instance_discussion(self):

		assert_that( courses.CourseInstance(), has_property( 'Discussions', not_none() ) )
		inst = courses.CourseInstance()
		assert_that( inst.Discussions, is_( same_instance( inst.Discussions )))

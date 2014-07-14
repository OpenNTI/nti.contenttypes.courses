#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

import unittest
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_not as does_not
from hamcrest import all_of
from hamcrest import has_length
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_property
from hamcrest import has_entries
from hamcrest import not_none
from hamcrest import none

from nti.externalization.tests import externalizes

import os.path
from nti.testing.matchers import validly_provides

from .._outline_parser import fill_outline_from_key
from ..outlines import PersistentCourseOutline as CourseOutline
from ..interfaces import ICourseOutline

from nti.contentlibrary.filesystem import FilesystemKey

from . import CourseLayerTest

class TestOutlineParser(CourseLayerTest):

	def test_parse(self):
		path = os.path.join( os.path.dirname(__file__),
							 'TestSynchronizeWithSubInstances',
							 'Spring2014',
							 'Gateway',
							 'course_outline.xml')
		key = FilesystemKey()
		key.absolute_path = path

		outline = CourseOutline()
		fill_outline_from_key(outline, key)
		assert_that( outline, validly_provides(ICourseOutline))

		unit_1 = outline['0']
		assert_that( unit_1, has_property('title', 'Introduction'))

		lesson_1 = unit_1["0"]
		assert_that( lesson_1.AvailableBeginning, is_(not_none()))
		assert_that( lesson_1.AvailableEnding, is_(not_none()))
		assert_that( lesson_1, has_property( 'title', '1. Defining Law and Justice' ) )
		assert_that( lesson_1, has_property('AvailableEnding', has_property('tzinfo', none())))
		assert_that( lesson_1, externalizes(has_entries('AvailableEnding', '2013-08-22T04:59:59Z',
														'title', '1. Defining Law and Justice',
														'description', '')))
		# Sub-lessons
		assert_that( lesson_1, has_length(1) )
		assert_that( lesson_1["0"], has_property('ContentNTIID', "tag:nextthought.com,2011-10:OU-HTML-DNE" ) )

		# This one is a stub
		lesson_2 = unit_1["1"]
		assert_that( lesson_2,
					 externalizes(
						 all_of(
							 does_not(has_key('ContentNTIID')),
							 has_entry('Class', 'CourseOutlineCalendarNode'))))


		# Doing it again does nothing...
		assert_that( outline, has_length(6) )

		fill_outline_from_key(outline, key)
		assert_that( outline, has_length(6) )

		# ...even if we set modification back
		outline.lastModified = -1

		fill_outline_from_key(outline, key)
		assert_that( outline, has_length(6) )

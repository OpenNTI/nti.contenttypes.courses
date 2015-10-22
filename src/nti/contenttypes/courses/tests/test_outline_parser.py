#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import all_of
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

from nti.testing.matchers import validly_provides

import os.path

from nti.contentlibrary.filesystem import FilesystemKey

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses._outline_parser import fill_outline_from_key
from nti.contenttypes.courses.outlines import PersistentCourseOutline as CourseOutline

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.externalization.tests import externalizes

class TestOutlineParser(CourseLayerTest):

	def test_parse(self):
		path = os.path.join(os.path.dirname(__file__),
							 'TestSynchronizeWithSubInstances',
							 'Spring2014',
							 'Gateway',
							 'course_outline.xml')
		key = FilesystemKey()
		key.absolute_path = path

		outline = CourseOutline()
		fill_outline_from_key(outline, key)
		assert_that(outline, validly_provides(ICourseOutline))

		unit_1 = outline['tag:nextthought.com,2011-10:OU-NTICourseUnit-CLC3403_LawAndJustice.course.unit.1']
		assert_that(unit_1, has_property('title', 'Introduction'))
		assert_that(unit_1, has_property('ntiid', 'tag:nextthought.com,2011-10:OU-NTICourseOutlineNode-CLC3403_LawAndJustice.course.unit.1'))

		lesson_1 = unit_1['tag:nextthought.com,2011-10:OU-NTICourseLesson-CLC3403_LawAndJustice.course.unit.1.0']
		assert_that(lesson_1.AvailableBeginning, is_(not_none()))
		assert_that(lesson_1.AvailableEnding, is_(not_none()))
		assert_that(lesson_1, has_property('title', '1. Defining Law and Justice'))
		assert_that(lesson_1, has_property('AvailableEnding', has_property('tzinfo', none())))
		assert_that(lesson_1, has_property('ntiid', 'tag:nextthought.com,2011-10:OU-NTICourseOutlineNode-CLC3403_LawAndJustice.course.unit.1.0'))
		assert_that(lesson_1, externalizes(has_entries(	'AvailableEnding', '2013-08-22T04:59:59Z',
														'title', '1. Defining Law and Justice',
														'NTIID', is_not(none()),
														'description', '')))

		# Sub-lessons
		assert_that(lesson_1, has_length(1))
		assert_that(lesson_1["tag:nextthought.com,2011-10:OU-NTICourseOutlineNode-CLC3403_LawAndJustice.course.unit.1.0.0"],
					has_property('ContentNTIID', "tag:nextthought.com,2011-10:OU-HTML-DNE"))

		# This one is a stub
		lesson_2 = unit_1["tag:nextthought.com,2011-10:OU-NTICourseOutlineNode-CLC3403_LawAndJustice.course.unit.1.1"]
		assert_that(lesson_2,
					 externalizes(
						 all_of(
							 does_not(has_key('ContentNTIID')),
							 has_entry('Class', 'CourseOutlineCalendarNode'))))

		unit_7 = outline['tag:nextthought.com,2011-10:OU-NTICourseOutlineNode-CLC3403_LawAndJustice.course.unit.7']
		assert_that(unit_7, has_property('title', 'Dateless Resources'))
		lesson_1 = unit_7["tag:nextthought.com,2011-10:OU-NTICourseOutlineNode-CLC3403_LawAndJustice.course.unit.7.0"]
		assert_that(lesson_1, has_property('AvailableEnding', is_(none())))
		assert_that(lesson_1, has_property('AvailableBeginning', is_(none())))

		# Doing it again does nothing...
		assert_that(outline, has_length(7))

		fill_outline_from_key(outline, key)
		assert_that(outline, has_length(7))

		# ...even if we set modification back
		outline.lastModified = -1

		fill_outline_from_key(outline, key)
		assert_that(outline, has_length(7))

	def test_parse_empty(self):

		class Key(object):
			lastModified = 99999999
			def readContentsAsETree(self):
				return self
			def iterchildren(self, tag=''):
				return iter(())

		outline = CourseOutline()
		key = Key()
		try:
			fill_outline_from_key(outline, key, xml_parent_name='foo')
			assert False
		except ValueError as e:
			assert_that(e.args,
						 is_(('No outline child in key',
							  key,
							  'foo')))

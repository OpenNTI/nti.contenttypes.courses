#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import has_property

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

import time
from datetime import datetime

import isodate

from zope.interface.interfaces import IMethod

from nti.coremetadata.interfaces import IRecordable
from nti.coremetadata.interfaces import ICalendarPublishable

from nti.contenttypes.courses import courses
from nti.contenttypes.courses import outlines
from nti.contenttypes.courses import interfaces

from nti.externalization.internalization import find_factory_for, \
	update_from_external_object
from nti.externalization.externalization import to_external_object

from nti.recorder.interfaces import ITransactionRecordHistory

from nti.contenttypes.courses.tests import CourseLayerTest

class TestCourseOutline(CourseLayerTest):

	def test_outline_implements(self):
		assert_that(outlines.CourseOutlineNode(), verifiably_provides(interfaces.ICourseOutlineNode))
		assert_that(outlines.CourseOutline(), verifiably_provides(interfaces.ICourseOutline))
		assert_that(outlines.CourseOutlineNode(), verifiably_provides(IRecordable))
		assert_that(outlines.CourseOutline(), verifiably_provides(IRecordable))

	def test_outline_tag_fields(self):
		fields = ('title', 'description', 'AvailableEnding', 'AvailableBeginning')
		for iface in (interfaces.ICourseOutlineNode,
					  interfaces.ICourseOutlineContentNode,
					  interfaces.ICourseOutlineCalendarNode):

			for name in fields:
				if name in iface:
					value = iface[name].queryTaggedValue(interfaces.TAG_HIDDEN_IN_UI)
					assert_that(value, is_(False))
					value = iface[name].queryTaggedValue(interfaces.TAG_REQUIRED_IN_UI)
					assert_that(value, is_(False))

			for k, v in iface.namesAndDescriptions(all=True):
				if k not in fields and not IMethod.providedBy(v):
					value = v.queryTaggedValue(interfaces.TAG_HIDDEN_IN_UI)
					assert_that(value, is_(True))

	def test_trx_history(self):
		node = outlines.CourseOutlineNode()
		history = ITransactionRecordHistory(node, None)
		assert_that(history, is_not(none()))

	def test_outline_containment(self):
		inst = courses.CourseInstance()
		outline = inst.Outline
		node = outlines.CourseOutlineNode()
		outline.append(node)
		node2 = outlines.CourseOutlineContentNode(ContentNTIID='tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.lec:01_LESSON',
												  AvailableBeginning=datetime.now())
		node.append(node2)

		assert_that(node, validly_provides(interfaces.ICourseOutlineNode))
		assert_that(node, validly_provides(ICalendarPublishable))
		assert_that(outline, validly_provides(interfaces.ICourseOutline))
		assert_that(inst, validly_provides(interfaces.ICourseInstance))

	def test_outline_externalizes(self):
		inst = courses.CourseInstance()
		outline = inst.Outline
		node = outlines.CourseOutlineNode()
		outline.append(node)
		outline.src = 'src/is/this'
		now = isodate.parse_datetime('2015-12-03T15:01:24Z')
		node2 = outlines.CourseOutlineContentNode(ContentNTIID='tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.lec:01_LESSON',
												  AvailableBeginning=now)
		outline.append(node2)

		ext_obj = to_external_object(inst)
		assert_that(ext_obj, has_entries('Class', 'CourseInstance',
										 'Outline', has_entries('src', 'src/is/this',
																'MimeType', 'application/vnd.nextthought.courses.courseoutline'),
										 'MimeType', 'application/vnd.nextthought.courses.courseinstance'))

		ext_obj = to_external_object(node2)
		assert_that(ext_obj, has_entries('Class', 'CourseOutlineContentNode',
										 'MimeType', 'application/vnd.nextthought.courses.courseoutlinecontentnode',
										 'ContentNTIID', u'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.lec:01_LESSON'))

		ext_obj['AvailableEnding'] = now.isoformat()
		ext_obj['AvailableBeginning'] = time.mktime(now.timetuple())  # change to float
		factory = find_factory_for(ext_obj)
		assert_that(factory, is_not(none()))
		inst = factory()
		update_from_external_object(inst, ext_obj)
		assert_that(inst, has_property('AvailableEnding'), is_(now))
		assert_that(inst, has_property('AvailableBeginning'), is_(now))

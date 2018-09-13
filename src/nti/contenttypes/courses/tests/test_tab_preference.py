#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import has_items
from hamcrest import instance_of

from persistent.list import PersistentList
from persistent.mapping import PersistentMapping

from nti.externalization.externalization import to_external_object

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from nti.contenttypes.courses.tab_preference import CourseTabPreferences

from nti.contenttypes.courses.tests import CourseLayerTest

class TestCourseTabPreferences(CourseLayerTest):

	def test_internalize(self):
		external = {
			"MimeType": "application/vnd.nextthought.courses.coursetabpreferences",
			"names": {"1": "a", "3": "b"},
			"order": ["1", "2"]
		}
		factory = find_factory_for(external)
		assert_that(factory, not_none())
		new_io = factory()
		modified = new_io.lastModified

		update_from_external_object(new_io, external)
		assert_that(new_io._names, instance_of(PersistentMapping))
		assert_that(new_io._order, instance_of(PersistentList))
		assert_that(new_io._names, has_entries({'1': 'a', '3': 'b'}))
		assert_that(new_io._order, has_items('1', '2'))
		assert_that(new_io.lastModified > modified, is_(True))

		update_from_external_object(new_io, {"names": None, "order": None})
		assert_that(new_io._names, instance_of(PersistentMapping))
		assert_that(new_io._order, instance_of(PersistentList))
		assert_that(new_io._names, has_length(0))
		assert_that(new_io._order, has_length(0))

		update_from_external_object(new_io, {"names": {"5": "ok"}})
		assert_that(new_io._names, instance_of(PersistentMapping))
		assert_that(new_io._order, instance_of(PersistentList))
		assert_that(new_io._names, has_length(1))
		assert_that(new_io._order, has_length(0))

		update_from_external_object(new_io, {"order": ['3', '4']})
		assert_that(new_io._names, instance_of(PersistentMapping))
		assert_that(new_io._order, instance_of(PersistentList))
		assert_that(new_io._names, has_length(1))
		assert_that(new_io._order, has_length(2))

	def test_externalize(self):
		obj = CourseTabPreferences()
		assert_that(obj._names, instance_of(PersistentMapping))
		assert_that(obj._order, instance_of(PersistentList))
		
		external = to_external_object(obj)
		assert_that(external, has_entries({'MimeType': 'application/vnd.nextthought.courses.coursetabpreferences',
										   'CreatedTime': not_none(),
										   'Last Modified': not_none(),
										   'names': has_length(0),
										   'order': has_length(0)}))

		obj.update_names({'1': 'a', '2': 'b'})
		obj.update_order(['2', '3'])
		assert_that(obj._names, instance_of(PersistentMapping))
		assert_that(obj._order, instance_of(PersistentList))
		
		external = to_external_object(obj)
		assert_that(external, has_entries({'MimeType': 'application/vnd.nextthought.courses.coursetabpreferences',
										   'names': has_entries({'1': 'a', '2': 'b'}),
										   'order': contains('2', '3')}))

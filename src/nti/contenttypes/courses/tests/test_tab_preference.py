#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import raises
from hamcrest import calling
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_items
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import instance_of
from hamcrest import has_properties

from persistent.list import PersistentList

from persistent.mapping import PersistentMapping

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.interfaces import ICourseTabPreferences

from nti.contenttypes.courses.tab_preference import CourseTabPreferences

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.externalization.externalization import to_external_object

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object


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
        
        new_io.clear()
        assert_that(new_io, has_properties('_names', has_length(0),
                                           '_order', has_length(0)))
        
        new_io.names = {"5": "ok"}
        new_io.order = ['3']
        assert_that(new_io, has_properties('names', has_length(1),
                                           'order', has_length(1)))

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

    def test_update_order(self):
        obj = CourseTabPreferences()
        obj.update_order(['2', '3'])
        assert_that(obj._order, instance_of(PersistentList))
        assert_that(obj._order, contains('2', '3'))

        obj.update_order(('2', '1'))
        assert_that(obj._order, instance_of(PersistentList))
        assert_that(obj._order, contains('2', '1'))

        assert_that(calling(obj.update_order).with_args(False), 
                    raises(TypeError, pattern="order must be a tuple or a list."))
        assert_that(calling(obj.update_order).with_args(None), 
                    raises(TypeError, pattern="order must be a tuple or a list."))
        assert_that(calling(obj.update_order).with_args("abc"), 
                    raises(TypeError, pattern="order must be a tuple or a list."))

    def test_annotation(self):
        course = CourseInstance()
        obj = ICourseTabPreferences(course)
        assert_that(obj, instance_of(CourseTabPreferences))
        assert_that(obj.__name__, is_("CourseTabPreferences"))
        assert_that(obj.__parent__, is_(course))

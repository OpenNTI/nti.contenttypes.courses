#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import contains_inanyorder
does_not = is_not

from nti.contenttypes.courses.courses import CourseInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel

from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import StandardExternalFields

from nti.contenttypes.courses.tests import CourseLayerTest

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE


class TestExternal(CourseLayerTest):

    def test_admin_level(self):
        level = CourseAdministrativeLevel()
        ext_obj = to_external_object(level, name='summary')
        assert_that(ext_obj, has_entries(MIMETYPE, CourseAdministrativeLevel.mime_type,
                                         CLASS, CourseAdministrativeLevel.__name__))
        assert_that(ext_obj, does_not(has_item(ITEMS)))

        level['course1'] = CourseInstance()
        level['course2'] = CourseInstance()
        level['course3'] = CourseInstance()
        ext_obj = to_external_object(level, name='summary')

        assert_that(ext_obj,
                    has_entry(ITEMS,
                              contains_inanyorder('course1', 'course2', 'course3')))

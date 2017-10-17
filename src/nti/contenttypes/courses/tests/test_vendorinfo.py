#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that
from hamcrest import has_property

from nti.testing.matchers import validly_provides

import unittest

from nti.contenttypes.courses import courses
from nti.contenttypes.courses import vendorinfo
from nti.contenttypes.courses import interfaces

from nti.contenttypes.courses.tests import CourseLayerTest


class TestVendorInfo(unittest.TestCase):

    def test_provides(self):
        assert_that(vendorinfo.DefaultCourseInstanceVendorInfo(),
                    validly_provides(interfaces.ICourseInstanceVenderInfo))

    def test_fresh_time(self):
        vi = vendorinfo.DefaultCourseInstanceVendorInfo()
        assert_that(vi, has_property('createdTime', 0))
        assert_that(vi, has_property('lastModified', 0))


class TestFunctionalVendorInfo(CourseLayerTest):

    def test_annotation(self):
        course = courses.CourseInstance()

        vi = interfaces.ICourseInstanceVenderInfo(course)
        assert_that(vi, is_(vendorinfo.DefaultCourseInstanceVendorInfo))
        assert_that(vi, has_property('__parent__', course))

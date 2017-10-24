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
from nti.testing.matchers import verifiably_provides

import unittest

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.contenttypes.courses.vendorinfo import DefaultCourseInstanceVendorInfo


class TestVendorInfo(unittest.TestCase):

    def test_provides(self):
        vendor = DefaultCourseInstanceVendorInfo()
        assert_that(vendor, validly_provides(ICourseInstanceVendorInfo))
        assert_that(vendor, verifiably_provides(ICourseInstanceVendorInfo))

    def test_fresh_time(self):
        vi = DefaultCourseInstanceVendorInfo()
        assert_that(vi, has_property('createdTime', 0))
        assert_that(vi, has_property('lastModified', 0))


class TestFunctionalVendorInfo(CourseLayerTest):

    def test_annotation(self):
        course = CourseInstance()
        vi = ICourseInstanceVendorInfo(course)
        assert_that(vi, is_(DefaultCourseInstanceVendorInfo))
        assert_that(vi, has_property('__parent__', course))

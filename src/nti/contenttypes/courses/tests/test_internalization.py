#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
does_not = is_not

import os
import codecs

import simplejson

from nti.contenttypes.courses.internalization import transform

from nti.contenttypes.courses.legacy_catalog import PersistentCourseCatalogLegacyEntry as CourseCatalogLegacyEntry

from nti.externalization.internalization import update_from_external_object

from nti.contenttypes.courses.tests import CourseLayerTest


class TestInternalization(CourseLayerTest):

    def setUp(self):
        path = os.path.join(os.path.dirname(__file__),
                            'course_info.json')
        self.path = path

    def test_trivial_parse(self):
        with codecs.open(self.path, "r", "utf-8") as fp:
            json_data = simplejson.load(fp)

        entry = CourseCatalogLegacyEntry()
        json_data = transform(json_data, entry, delete=False) 
        update_from_external_object(entry, json_data)

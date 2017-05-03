#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
does_not = is_not

import os
import codecs

import simplejson

from nti.contenttypes.courses.legacy_catalog import PersistentCourseCatalogLegacyEntry

from nti.externalization.externalization import toExternalObject
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

        entry = PersistentCourseCatalogLegacyEntry()
        update_from_external_object(entry, json_data)
        ext_obj = toExternalObject(entry)
        assert_that(ext_obj,
                    has_entries('Preview', False,
                                "StartDate", "2016-08-22T05:00:00Z",
                                "EndDate", "2016-12-19T05:00:00Z",
                                "Schedule", has_entries("days", ["MTWRF"],
                                                        "times", has_length(2)),
                                "Instructors", has_length(5),
                                "ProviderUniqueID", "BIOL 2124",
                                "ProviderDepartmentTitle", "Department of Biology, University of Oklahoma",
                                "description", is_not(none()),
                                "Credit", has_length(1),
                                "title", "Human Physiology",
                                "Video", "kaltura://1500101/0_gpczmps5/"))

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import all_of
from hamcrest import is_not
from hamcrest import equal_to
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_properties
from hamcrest import contains_string
does_not = is_not

from nti.testing.matchers import verifiably_provides

import os.path

from datetime import timedelta

from zope.interface.common.idatetime import IDateTime

from nti.contentlibrary.filesystem import FilesystemKey

from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_key
from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_json

from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance

from nti.contenttypes.courses.internalization import parse_duration

from nti.contenttypes.courses.legacy_catalog import ICourseCatalogLegacyEntry
from nti.contenttypes.courses.legacy_catalog import PersistentCourseCatalogLegacyEntry as CourseCatalogLegacyEntry

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.externalization.tests import externalizes


class TestCatalogParser(CourseLayerTest):

    def setUp(self):
        path = os.path.join(os.path.dirname(__file__),
                            'TestSynchronizeWithSubInstances',
                            'Spring2014',
                            'Gateway',
                            'course_info.json')
        key = FilesystemKey()
        key.absolute_path = path
        self.key = key

    def test_parse_duration(self):
        duration = parse_duration(u'1 Weeks')
        assert_that(duration, is_not(none()))

        duration = parse_duration(u'118 Days')
        assert_that(duration, is_not(none()))

        duration = parse_duration(u'P118D')
        assert_that(duration, is_not(none()))

    def test_trivial_parse(self):
        key = self.key

        entry = CourseCatalogLegacyEntry()
        fill_entry_from_legacy_key(entry, key)

        assert_that(entry,
                    has_properties('ProviderUniqueID', 'CLC 3403',
                                   'Title', 'Law and Justice',
                                   'DisableOverviewCalendar', True))
        assert_that(entry, verifiably_provides(ICourseCatalogLegacyEntry))

        richDescription = entry.RichDescription
        assert_that(richDescription,
                    all_of(contains_string('<strong>'), contains_string('<li>')))

        instructors = entry.Instructors
        assert_that(instructors, has_length(1))
        assert_that(instructors[0], 
                    has_properties("Name", 'Dr. Kyle Harper',
                                   "username", "harp4162",
                                   'JobTitle', 'Associate Professor of Classics',
                                   'defaultphoto', "/images/Harper.png",
                                   'Biography', "Senior Vice President and Provost",))

        assert_that(entry,
                    externalizes(has_entries(
                                    'MimeType', 'application/vnd.nextthought.courses.persistentcoursecataloglegacyentry',
                                    'DisableOverviewCalendar', True,
                                    'RichDescription', contains_string('<strong>'))))

        fill_entry_from_legacy_key(entry, key)
        assert_that(entry,
                    has_properties('ProviderUniqueID', 'CLC 3403',
                                   'Title', 'Law and Justice',
                                   'AdditionalProperties', {"section": "parent"}))

    def test_start_and_duration_parse(self):
        key = self.key

        entry = CourseCatalogLegacyEntry()
        fill_entry_from_legacy_key(entry, key)

        json = key.readContentsAsJson()
        json['startDate'] = u'2015-06-29T05:00:00+00:00'
        del json['duration']

        fill_entry_from_legacy_json(entry, json)

        assert_that(entry.StartDate, is_not(none()))
        assert_that(entry.Duration, is_(none()))
        assert_that(entry.EndDate, is_(none()))

        json['duration'] = u'1 Weeks'
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry.Duration, equal_to(timedelta(days=7)))
        assert_that(entry.EndDate,
                    equal_to(IDateTime('2015-07-06T05:00:00+00:00')))

        # Now pop
        del json['startDate']
        json.pop('StartDate', None)
        fill_entry_from_legacy_json(entry, json)

        assert_that(entry.StartDate, none())
        assert_that(entry.Duration, is_not(none()))
        assert_that(entry.EndDate, none())

    def test_start_and_end_date_parse(self):
        key = self.key

        entry = CourseCatalogLegacyEntry()
        fill_entry_from_legacy_key(entry, key)

        json = key.readContentsAsJson()
        json['startDate'] = u'2015-06-29T05:00:00+00:00'
        json['duration'] = u'1 Weeks'
        json['endDate'] = u'2015-06-30T05:00:00+00:00'
        fill_entry_from_legacy_json(entry, json)

        assert_that(entry.StartDate,
                    equal_to(IDateTime('2015-06-29T05:00:00+00:00')))
        assert_that(entry.Duration,
                    equal_to(timedelta(days=7)))
        assert_that(entry.EndDate,
                    equal_to(IDateTime('2015-06-30T05:00:00+00:00')))

    def test_toggle_non_public(self):
        key = self.key

        entry = CourseCatalogLegacyEntry()
        fill_entry_from_legacy_key(entry, key)

        json = key.readContentsAsJson()

        json['is_non_public'] = False
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry,
                    does_not(verifiably_provides(INonPublicCourseInstance)))

        json['is_non_public'] = True
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry, verifiably_provides(INonPublicCourseInstance))

        json['is_non_public'] = False
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry,
                    does_not(verifiably_provides(INonPublicCourseInstance)))

        # Back to true
        json['is_non_public'] = True
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry, verifiably_provides(INonPublicCourseInstance))

        # Now simply missing, nothing changes
        del json['is_non_public']
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry, verifiably_provides(INonPublicCourseInstance))

    def test_toggle_anonymously_accessible(self):
        key = self.key

        entry = CourseCatalogLegacyEntry()
        fill_entry_from_legacy_key(entry, key)

        json = key.readContentsAsJson()

        json['is_anonymously_but_not_publicly_accessible'] = False
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry,
                    does_not(verifiably_provides(IAnonymouslyAccessibleCourseInstance)))

        json['is_anonymously_but_not_publicly_accessible'] = True
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry,
                    verifiably_provides(IAnonymouslyAccessibleCourseInstance))

        json['is_anonymously_but_not_publicly_accessible'] = False
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry,
                    does_not(verifiably_provides(IAnonymouslyAccessibleCourseInstance)))

        # Back to true
        json['is_anonymously_but_not_publicly_accessible'] = True
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry,
                    verifiably_provides(IAnonymouslyAccessibleCourseInstance))

        # Now simply missing and nothing changes
        del json['is_anonymously_but_not_publicly_accessible']
        fill_entry_from_legacy_json(entry, json)
        assert_that(entry, 
                    verifiably_provides(IAnonymouslyAccessibleCourseInstance))

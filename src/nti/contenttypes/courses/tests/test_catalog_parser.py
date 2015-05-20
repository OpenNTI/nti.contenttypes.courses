#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import equal_to
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_properties
does_not = is_not

import os.path

from datetime import timedelta

from zope.interface.common.idatetime import IDateTime

from nti.contentlibrary.filesystem import FilesystemKey

from nti.contenttypes.courses.interfaces import INonPublicCourseInstance

from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_key
from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_json

from nti.contenttypes.courses.legacy_catalog import ICourseCatalogLegacyEntry

from nti.contenttypes.courses.legacy_catalog import PersistentCourseCatalogLegacyEntry as CourseCatalogLegacyEntry

from nti.externalization.tests import externalizes

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.testing.matchers import verifiably_provides

class TestCatalogParser(CourseLayerTest):

	def setUp(self):
		path = os.path.join( os.path.dirname(__file__),
							 'TestSynchronizeWithSubInstances',
							 'Spring2014',
							 'Gateway',
							 'course_info.json')
		key = FilesystemKey()
		key.absolute_path = path
		self.key = key

	def test_trivial_parse(self):
		key = self.key

		entry = CourseCatalogLegacyEntry()
		fill_entry_from_legacy_key(entry, key)

		assert_that( entry,
					 has_properties( 'ProviderUniqueID', 'CLC 3403 S014',
									 'DisplayName', 'CLC 3403',
									 'Title', 'Law and Justice',
									 'DisableOverviewCalendar', True) )
		assert_that(entry, verifiably_provides(ICourseCatalogLegacyEntry))

		assert_that( entry,
					 externalizes( has_entries(
							 'DisableOverviewCalendar', True) ) ) 
		
		fill_entry_from_legacy_key(entry, key)
		assert_that( entry,
					 has_properties( 'ProviderUniqueID', 'CLC 3403 S014',
									 'Title', 'Law and Justice') )
		
	def test_start_and_duration_parse(self):
		key = self.key

		entry = CourseCatalogLegacyEntry()
		fill_entry_from_legacy_key(entry, key)

		json = key.readContentsAsJson()
		json['startDate'] = '2015-06-29T05:00:00+00:00'
		del json['duration']
		
		fill_entry_from_legacy_json(entry, json)
		
		assert_that(entry.StartDate, is_not(none))
		assert_that(entry.Duration, none)
		assert_that(entry.EndDate, is_not(none))
		
		json['duration'] = '1 Weeks'
		fill_entry_from_legacy_json(entry, json)
		assert_that(entry.Duration, equal_to(timedelta(days=7)))
		assert_that(entry.EndDate, equal_to(IDateTime('2015-07-06T05:00:00+00:00')))
		
	def test_start_and_end_date_parse(self):
		key = self.key

		entry = CourseCatalogLegacyEntry()
		fill_entry_from_legacy_key(entry, key)

		json = key.readContentsAsJson()
		json['startDate'] = '2015-06-29T05:00:00+00:00'
		json['duration'] = '1 Weeks'
		json['endDate'] = '2015-06-30T05:00:00+00:00'
		fill_entry_from_legacy_json(entry, json)
		
		assert_that(entry.StartDate, equal_to(IDateTime('2015-06-29T05:00:00+00:00')))
		assert_that(entry.Duration, equal_to(timedelta(days=7)))
		assert_that(entry.EndDate, equal_to(IDateTime('2015-06-30T05:00:00+00:00')))

	def test_toggle_non_public(self):
		key = self.key

		entry = CourseCatalogLegacyEntry()
		fill_entry_from_legacy_key(entry, key)

		json = key.readContentsAsJson()

		json['is_non_public'] = True
		fill_entry_from_legacy_json(entry, json)
		assert_that( entry, verifiably_provides(INonPublicCourseInstance))

		json['is_non_public'] = False
		fill_entry_from_legacy_json(entry, json)
		assert_that( entry, does_not(verifiably_provides(INonPublicCourseInstance)))

		# Back to true
		json['is_non_public'] = True
		fill_entry_from_legacy_json(entry, json)
		assert_that( entry, verifiably_provides(INonPublicCourseInstance))

		# Now simply missing
		del json['is_non_public']
		fill_entry_from_legacy_json(entry, json)
		assert_that( entry, does_not(verifiably_provides(INonPublicCourseInstance)))

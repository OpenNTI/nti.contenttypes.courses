#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

import unittest
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_not as does_not
from hamcrest import all_of
from hamcrest import has_length
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_properties
from hamcrest import has_entries
from hamcrest import not_none
from hamcrest import none

from nti.externalization.tests import externalizes

import os.path
from nti.testing.matchers import verifiably_provides

from .._catalog_entry_parser import fill_entry_from_legacy_key
from .._catalog_entry_parser import fill_entry_from_legacy_json
from ..legacy_catalog import PersistentCourseCatalogLegacyEntry as CourseCatalogLegacyEntry
from ..legacy_catalog import ICourseCatalogLegacyEntry
from ..interfaces import INonPublicCourseInstance

from nti.contentlibrary.filesystem import FilesystemKey

from . import CourseLayerTest

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
					 has_properties( 'ProviderUniqueID', 'CLC 3403',
									 'Title', 'Law and Justice') )
		assert_that(entry, verifiably_provides(ICourseCatalogLegacyEntry))

		fill_entry_from_legacy_key(entry, key)
		assert_that( entry,
					 has_properties( 'ProviderUniqueID', 'CLC 3403',
									 'Title', 'Law and Justice') )

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

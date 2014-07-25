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
from hamcrest import none
from hamcrest import has_entry
from hamcrest import has_property

from nti.testing import base
from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

import isodate

from ..catalog import GlobalCourseCatalog
from ..catalog import CourseCatalogFolder
from ..catalog import CourseCatalogEntry
from ..legacy_catalog import _CourseSubInstanceCatalogLegacyEntry
from ..legacy_catalog import CourseCatalogLegacyEntry
from ..interfaces import IGlobalCourseCatalog
from ..interfaces import ICourseCatalog
from ..interfaces import ICourseCatalogEntry
from zope.location.interfaces import ILocation

class TestCatalog(unittest.TestCase):

	def test_global_catalog(self):
		assert_that(GlobalCourseCatalog(),
					validly_provides(IGlobalCourseCatalog))

	def test_catalog_implements(self):
		assert_that(CourseCatalogFolder(),
					validly_provides(ICourseCatalog))

	def test_entry_implements(self):
		assert_that(CourseCatalogEntry(),
					verifiably_provides(ICourseCatalogEntry))
		assert_that(CourseCatalogEntry(),
					validly_provides(ILocation))

		assert_that(_CourseSubInstanceCatalogLegacyEntry(),
					validly_provides(ILocation))


	def test_entry_timestamps(self):
		cce = CourseCatalogEntry()
		assert_that( cce, has_property('lastModified', 0 ))
		assert_that( cce, has_property('createdTime', 0 ))

		lcce = _CourseSubInstanceCatalogLegacyEntry()
		assert_that( lcce, has_property('lastModified', 0 ))
		assert_that( lcce, has_property('createdTime', 0 ))

		lcce._next_entry = cce
		assert_that( lcce, has_property('lastModified', 0 ))
		assert_that( lcce, has_property('createdTime', 0 ))

		cce.lastModified = cce.createdTime = 42

		assert_that( cce, has_property('lastModified', 42 ))
		assert_that( cce, has_property('createdTime', 42 ))

		# but they don't propagate down
		assert_that( lcce, has_property('lastModified', 0 ))
		assert_that( lcce, has_property('createdTime', 0 ))

	def test_preview(self):
		cce = CourseCatalogLegacyEntry()
		assert_that( cce, has_property('Preview', is_(none())))

		lcce = _CourseSubInstanceCatalogLegacyEntry()
		assert_that( lcce, has_property('Preview', is_(none())))

		lcce._next_entry = cce
		assert_that( lcce, has_property('Preview', is_(none())))

		cce.Preview = True

		assert_that( lcce, has_property('Preview', is_(True)))

		lcce.StartDate = isodate.parse_datetime('2001-01-01T00:00')
		assert_that( lcce, has_property('Preview', is_(False)))

		lcce.Preview = True
		assert_that( lcce, has_property('Preview', is_(True)))

		del lcce.Preview
		assert_that( lcce, has_property('Preview', is_(False)))

		del lcce.StartDate
		assert_that( lcce, has_property('Preview', is_(True)))

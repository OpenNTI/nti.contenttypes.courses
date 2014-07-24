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
from hamcrest import has_key
from hamcrest import has_entry

from nti.testing import base
from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

from ..catalog import GlobalCourseCatalog
from ..catalog import CourseCatalogFolder
from ..catalog import CourseCatalogEntry
from ..legacy_catalog import _CourseSubInstanceCatalogLegacyEntry
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

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
from nti.testing import matchers

import os.path

from .. import catalog
from .._synchronize import synchronize_catalog_from_root
from ..interfaces import ICourseInstanceVendorInfo
from nti.contentlibrary import filesystem
from nti.contentlibrary.library import EmptyLibrary
from nti.contentlibrary.interfaces import IContentPackageLibrary
from zope import component


from . import CourseLayerTest
from nti.externalization.tests import externalizes

class TestFunctionalSynchronize(CourseLayerTest):

	def setUp(self):
		self.library = EmptyLibrary()
		component.getGlobalSiteManager().registerUtility(self.library, IContentPackageLibrary)

	def tearDown(self):
		component.getGlobalSiteManager().unregisterUtility(self.library, IContentPackageLibrary)


	def test_synchronize_with_sub_instances(self):
		root_name ='TestSynchronizeWithSubInstances'
		absolute_path = os.path.join( os.path.dirname( __file__ ),
									  root_name )
		bucket = filesystem.FilesystemBucket(name=root_name)
		bucket.absolute_path = absolute_path

		folder = catalog.CourseCatalogFolder()

		synchronize_catalog_from_root(folder, bucket)

		# Now check that we get the structure we expect
		spring = folder['Spring2014']
		gateway = spring['Gateway']

		assert_that( ICourseInstanceVendorInfo(gateway),
					 has_entry( 'OU', has_entry('key', 42) ) )

		sec1 = gateway.SubInstances['01']
		assert_that( ICourseInstanceVendorInfo(sec1),
					 has_entry( 'OU', has_entry('key2', 72) ) )

		assert_that(sec1.ContentPackageBundle,
					is_(gateway.ContentPackageBundle))

		assert_that( sec1,
					 externalizes( has_entry(
						 'Class', 'CourseInstance' ) ) )

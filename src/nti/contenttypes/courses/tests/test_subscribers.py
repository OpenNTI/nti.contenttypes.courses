#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import same_instance

import os

from zope import component

from zope.site.folder import Folder
from zope.site.site import LocalSiteManager
from zope.site.interfaces import NewLocalSite

from nti.contentlibrary import filesystem
from nti.contentlibrary import interfaces as lib_interfaces
from nti.contentlibrary import subscribers as lib_subscribers
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo

from nti.contenttypes.courses.tests import CourseLayerTest

class TestFunctionalSubscribers(CourseLayerTest):

	def setUp(self):
		global_library = self.global_library = filesystem.GlobalFilesystemContentPackageLibrary(
			os.path.join(os.path.dirname(__file__), 'test_subscribers' ))
		global_library.syncContentPackages()

		component.getGlobalSiteManager().registerUtility( global_library,
														  provided=IContentPackageLibrary )

	def tearDown(self):
		component.getGlobalSiteManager().unregisterUtility( self.global_library,
															provided=IContentPackageLibrary )


	def test_install_site_library_instals_catalog(self):

		site = Folder()
		site.__name__ = 'localsite'
		sm = LocalSiteManager(site)

		site.setSiteManager(sm)

		site_lib = lib_subscribers.install_site_content_library( sm, NewLocalSite(sm))

		assert_that( sm.getUtility(lib_interfaces.IContentUnitAnnotationUtility),
					 is_not( component.getUtility(lib_interfaces.IContentUnitAnnotationUtility)) )

		assert_that( sm.getUtility(lib_interfaces.IContentPackageLibrary),
					 is_( same_instance(site_lib) ))

		# And we also installed and synced the catalog
		folder = sm.getUtility(ICourseCatalog)

		spring = folder['Spring2014']
		gateway = spring['Gateway']

		assert_that( ICourseInstanceVendorInfo(gateway),
					 has_entry( 'OU', has_entry('key', 42) ) )

		sec1 = gateway.SubInstances['01']
		assert_that( ICourseInstanceVendorInfo(sec1),
					 has_entry( 'OU', has_entry('key2', 72) ) )

		assert_that(sec1.ContentPackageBundle,
					is_(gateway.ContentPackageBundle))

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
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

from zope.site.interfaces import NewLocalSite

from zope.site.site import LocalSiteManager

from nti.contentlibrary.filesystem import GlobalFilesystemContentPackageLibrary

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentUnitAnnotationUtility

from nti.contentlibrary.subscribers import install_site_content_library

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo

from nti.contenttypes.courses.tests import CourseLayerTest


class TestFunctionalSubscribers(CourseLayerTest):

    def setUp(self):
        path = os.path.join(os.path.dirname(__file__), 'test_subscribers')
        global_library = GlobalFilesystemContentPackageLibrary(path)
        global_library.syncContentPackages()

        self.global_library = global_library
        component.getGlobalSiteManager().registerUtility(global_library,
                                                         provided=IContentPackageLibrary)

    def tearDown(self):
        component.getGlobalSiteManager().unregisterUtility(self.global_library,
                                                           provided=IContentPackageLibrary)

    def test_install_site_library_installs_catalog(self):

        site = Folder()
        site.__name__ = u'localsite'
        sm = LocalSiteManager(site)

        site.setSiteManager(sm)

        site_lib = install_site_content_library(sm, NewLocalSite(sm))

        assert_that(sm.getUtility(IContentUnitAnnotationUtility),
                    is_not(component.getUtility(IContentUnitAnnotationUtility)))

        assert_that(sm.getUtility(IContentPackageLibrary),
                    is_(same_instance(site_lib)))

        # And we also installed and synced the catalog
        folder = sm.getUtility(ICourseCatalog)

        spring = folder['Spring2014']
        gateway = spring['Gateway']

        assert_that(ICourseInstanceVendorInfo(gateway),
                    has_entry('OU', has_entry('key', 42)))

        sec1 = gateway.SubInstances['01']
        assert_that(ICourseInstanceVendorInfo(sec1),
                    has_entry('OU', has_entry('key2', 72)))

        assert_that(sec1.ContentPackageBundle,
                    is_(gateway.ContentPackageBundle))

        assert_that(ICourseCatalogEntry(gateway).ProviderUniqueID,
                    is_('CLC 3403'))
        assert_that(ICourseCatalogEntry(sec1).ProviderUniqueID,
                    is_('CLC 3403-01'))
        # Inherits from the parent
        sec2 = gateway.SubInstances['02']
        assert_that(ICourseCatalogEntry(sec2).ProviderUniqueID,
                    is_('CLC 3403'))

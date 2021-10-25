#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904
from hamcrest import has_length
from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import same_instance

import os

from zope import component

from zope.intid import IIntIds

from zope.site.folder import Folder

from zope.site.interfaces import NewLocalSite

from zope.site.site import LocalSiteManager

from nti.contentlibrary.filesystem import GlobalFilesystemContentPackageLibrary

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentUnitAnnotationUtility

from nti.contentlibrary.subscribers import install_site_content_library

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.contenttypes.courses.utils import get_enrollment_records

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User

from nti.intid.common import addIntId


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


class TestRemoveIndexedEnrollments(CourseLayerTest):

    def _add_course(self, course_title, ds_folder):
        course = ContentCourseInstance()
        entry = ICourseCatalogEntry(course)
        entry.title = course_title
        entry.ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-%s' % course_title
        ds_folder._p_jar.add(course)
        addIntId(course)
        return (course, entry)

    def _enroll(self, user, course, enrollment_catalog, intids):
        enrollments = ICourseEnrollmentManager(course)
        record = enrollments.enroll(user)
        enrollment_catalog.index_doc(intids.getId(record), record)
        return record

    @WithMockDSTrans
    def test_user_deletion_updates_index(self):
        ds_folder = self.ds.dataserver_folder
        intids = component.queryUtility(IIntIds)
        enrollment_catalog = get_enrollment_catalog()

        user1 = User.create_user(username=u'user001')

        result = get_enrollment_records(usernames=('user001',))
        assert_that(result, has_length(0))

        course1, entry1 = self._add_course(u'course1', ds_folder)

        self._enroll(user1, course1, enrollment_catalog, intids)

        result = get_enrollment_records(usernames=('user001',))
        assert_that(result, has_length(1))

        User.delete_user(username=u'user001')

        result = get_enrollment_records(usernames=('user001',))
        assert_that(result, has_length(0))


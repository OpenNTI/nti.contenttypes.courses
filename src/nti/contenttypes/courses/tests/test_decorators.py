#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries

from zope import interface

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses.catalog import CourseCatalogFolder

from nti.contenttypes.courses.creator import create_course

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance

from nti.contenttypes.courses.tests import mock
from nti.contenttypes.courses.tests import CourseLayerTest

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.externalization.externalization import to_external_object

from nti.site.folder import HostPolicyFolder


class TestDecorators(CourseLayerTest):

    @mock.patch('nti.contenttypes.courses.creator.library_root')
    def test_decorators(self, mock_lr):
        root = FilesystemBucket(name=u"root")
        root.absolute_path = '/tmp'
        mock_lr.return_value = root

        folder = HostPolicyFolder()
        folder.__name__ = u'bleach.org'
        catalog = CourseCatalogFolder()
        catalog.__name__ = u'Courses'
        catalog.__parent__ = folder
        course = create_course(u"Bleach", u"Shikai", catalog, writeout=True)
        interface.alsoProvides(course, INonPublicCourseInstance)

        ext_obj = to_external_object(course)
        assert_that(ext_obj,
                    has_entries('AdminLevel', 'Bleach',
                                'Site', 'bleach.org',
                                'is_non_public', True))

        # No title means we use existing realname
        ext_scopes = to_external_object(course.SharingScopes)
        ext_public = ext_scopes.get(ES_PUBLIC)
        assert_that(ext_public, has_entry('realname', ES_PUBLIC))
        ext_credit = ext_scopes.get(ES_CREDIT_DEGREE)
        assert_that(ext_credit, has_entry('realname', ES_CREDIT_DEGREE))

        # With course title
        entry = ICourseCatalogEntry(course)
        entry.title = u'my course title'
        ext_scopes = to_external_object(course.SharingScopes)
        ext_public = ext_scopes.get(ES_PUBLIC)
        assert_that(ext_public, has_entry('realname', entry.title))
        ext_credit = ext_scopes.get(ES_CREDIT_DEGREE)
        assert_that(ext_credit, has_entry('realname',
                                          u'%s (%s)' % (entry.title, ES_CREDIT_DEGREE)))

        # If realname set we use that
        public_scope = course.SharingScopes.get(ES_PUBLIC)
        fn = IFriendlyNamed(public_scope)
        fn.realname = u'new realname'
        ext_scopes = to_external_object(course.SharingScopes)
        ext_public = ext_scopes.get(ES_PUBLIC)
        assert_that(ext_public, has_entry('realname', fn.realname))
        ext_credit = ext_scopes.get(ES_CREDIT_DEGREE)
        assert_that(ext_credit, has_entry('realname',
                                          u'%s (%s)' % (entry.title, ES_CREDIT_DEGREE)))

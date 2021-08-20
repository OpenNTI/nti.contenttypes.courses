#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import same_instance
does_not = is_not

import os
import shutil
import tempfile

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses.catalog import CourseCatalogFolder

from nti.contenttypes.courses.creator import create_course
from nti.contenttypes.courses.creator import make_directories
from nti.contenttypes.courses.creator import install_admin_level
from nti.contenttypes.courses.creator import create_course_subinstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.tests import mock
from nti.contenttypes.courses.tests import CourseLayerTest


class TestCreator(CourseLayerTest):

    @mock.patch('nti.contenttypes.courses.creator.library_root')
    def test_install_admin_level(self, mock_lr):
        catalog = CourseCatalogFolder()
        catalog.__name__ = u'Courses'

        tmp_dir = tempfile.mkdtemp()
        try:
            root = FilesystemBucket(name=u"root")
            root.absolute_path = tmp_dir
            mock_lr.return_value = root
            # create courses place
            courses_path = os.path.join(tmp_dir, 'Courses')
            make_directories(courses_path)

            # writeout
            level = install_admin_level(u"Bleach", catalog=catalog)
            assert_that(level, is_not(none()))
            output = os.path.join(courses_path, 'Bleach')
            assert_that(level,
                        has_property('root', has_property('absolute_path', is_(output))))
            assert_that(os.path.exists(output), is_(True))

            # not writeout
            level = install_admin_level(u"Titan",
                                        catalog=catalog,
                                        writeout=False)
            assert_that(level, is_not(none()))
            output = os.path.join(courses_path, 'Titan')
            assert_that(level,
                        has_property('root', has_property('absolute_path', is_(output))))
            assert_that(os.path.exists(output), is_(False))

            level2 = install_admin_level(u"Titan",
                                         catalog=catalog,
                                         writeout=False)
            assert_that(level2, is_(same_instance(level)))
        finally:
            shutil.rmtree(tmp_dir)

    @mock.patch('nti.contenttypes.courses.creator.library_root')
    def test_create_course(self, mock_lr):
        catalog = CourseCatalogFolder()
        catalog.__name__ = u'Courses'

        tmp_dir = tempfile.mkdtemp()
        try:
            root = FilesystemBucket(name=u"root")
            root.absolute_path = tmp_dir
            mock_lr.return_value = root
            # create courses place
            courses_path = os.path.join(tmp_dir, u'Courses')
            make_directories(courses_path)

            # writeout
            course = create_course(u"Bleach", u"Shikai", catalog, writeout=True)
            assert_that(course, is_not(none()))
            assert_that(course.ContentPackageBundle, is_not(none()))
            assert_that(course.ContentPackageBundle.ntiid, is_not(none()))
            output = os.path.join(courses_path, 'Bleach/Shikai')
            assert_that(course,
                        has_property('root', has_property('absolute_path', is_(output))))
            assert_that(os.path.exists(output), is_(True))

            entry = ICourseCatalogEntry(course)
            assert_that(entry.createdTime, is_not(0))

            # not writeout
            output = os.path.join(courses_path, 'Bleach/Bankai')
            make_directories(output)
            course = create_course(u"Bleach", u"Bankai", catalog, writeout=False)
            assert_that(course, is_not(none()))
            assert_that(course.ContentPackageBundle, is_not(none()))
            assert_that(course.ContentPackageBundle.ntiid, is_not(none()))
            assert_that(course,
                        has_property('root', has_property('absolute_path', is_('%s.1' % output))))
            
            # Absolute path should be relative and not fixed
            assert_that(course.root.__dict__, does_not(has_item('absolute_path')))
            
            # Unicode
            course = create_course(u"Bleach", u"Ω New Designer Review Ω", catalog, writeout=True)
            assert_that(course, is_not(none()))
            course_path = os.path.join(courses_path, 'Bleach/O_New_Designer_Review_O')
            assert_that(course,
                        has_property('root', has_property('absolute_path', 
                                                          is_(course_path))))
            
            # Distinct course key but will be similar filesystem key
            course = create_course(u"Bleach", u"Ω_New_Designer Review Ω", catalog, writeout=True)
            assert_that(course, is_not(none()))
            course_path = os.path.join(courses_path, 'Bleach/O_New_Designer_Review_O.1')
            assert_that(course,
                        has_property('root', has_property('absolute_path', 
                                                          is_(course_path))))
            
            course = create_course(u"Bleach", u"O_New_Designer Review O", catalog, writeout=True)
            assert_that(course, is_not(none()))
            course_path = os.path.join(courses_path, 'Bleach/O_New_Designer_Review_O.2')
            assert_that(course,
                        has_property('root', has_property('absolute_path', 
                                                          is_(course_path))))
        finally:
            shutil.rmtree(tmp_dir)

    @mock.patch('nti.contenttypes.courses.creator.library_root')
    def test_create_course_subinstance(self, mock_lr):
        catalog = CourseCatalogFolder()
        catalog.__name__ = u'Courses'

        tmp_dir = tempfile.mkdtemp()
        try:
            root = FilesystemBucket(name=u"root")
            root.absolute_path = tmp_dir
            mock_lr.return_value = root
            # create courses place
            courses_path = os.path.join(tmp_dir, 'Courses')
            make_directories(courses_path)

            # writeout
            course = create_course(u"Bleach", u"Shikai", catalog, writeout=True)
            subinstance = create_course_subinstance(course, u'Water', writeout=True)
            assert_that(subinstance, is_not(none()))
            output = os.path.join(courses_path, 'Bleach/Shikai/Sections/Water')
            assert_that(subinstance,
                        has_property('root', has_property('absolute_path', is_(output))))
            assert_that(os.path.exists(output), is_(True))

            # not writeout
            output = os.path.join(courses_path, 'Bleach/Shikai/Sections/Ice')
            subinstance = create_course_subinstance(course, u'Ice', writeout=False)
            assert_that(subinstance, is_not(none()))
            assert_that(subinstance,
                        has_property('root', has_property('absolute_path', is_(output))))
            assert_that(os.path.exists(output), is_(False))
        finally:
            shutil.rmtree(tmp_dir)

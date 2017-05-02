#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import same_instance

import os
import shutil
import tempfile

import fudge

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses.creator import create_course
from nti.contenttypes.courses.creator import make_directories
from nti.contenttypes.courses.creator import install_admin_level
from nti.contenttypes.courses.creator import create_course_subinstance

from nti.externalization.interfaces import LocatedExternalDict

from nti.contenttypes.courses.tests import CourseLayerTest


class TestCreator(CourseLayerTest):

    @fudge.patch('nti.contenttypes.courses.creator.library_root')
    def test_install_admin_level(self, mock_lr):
        catalog = LocatedExternalDict()
        catalog.__name__ = u'Courses'

        tmp_dir = tempfile.mkdtemp()
        try:
            root = FilesystemBucket(name=u"root")
            root.absolute_path = tmp_dir
            mock_lr.is_callable().with_args().returns(root)
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

    @fudge.patch('nti.contenttypes.courses.creator.library_root')
    def test_create_course(self, mock_lr):
        catalog = LocatedExternalDict()
        catalog.__name__ = u'Courses'

        tmp_dir = tempfile.mkdtemp()
        try:
            root = FilesystemBucket(name=u"root")
            root.absolute_path = tmp_dir
            mock_lr.is_callable().with_args().returns(root)
            # create courses place
            courses_path = os.path.join(tmp_dir, u'Courses')
            make_directories(courses_path)

            # writeout
            course = create_course(u"Bleach", u"Shikai", catalog, writeout=True)
            assert_that(course, is_not(none()))
            output = os.path.join(courses_path, 'Bleach/Shikai')
            assert_that(course,
                        has_property('root', has_property('absolute_path', is_(output))))
            assert_that(os.path.exists(output), is_(True))

            # not writeout
            output = os.path.join(courses_path, 'Bleach/Bankai')
            make_directories(output)
            course = create_course(u"Bleach", u"Bankai", catalog, writeout=False)
            assert_that(course, is_not(none()))
            assert_that(course,
                        has_property('root', has_property('absolute_path', is_(output))))
        finally:
            shutil.rmtree(tmp_dir)
            
    @fudge.patch('nti.contenttypes.courses.creator.library_root')
    def test_create_course_subinstance(self, mock_lr):
        catalog = LocatedExternalDict()
        catalog.__name__ = u'Courses'

        tmp_dir = tempfile.mkdtemp()
        try:
            root = FilesystemBucket(name=u"root")
            root.absolute_path = tmp_dir
            mock_lr.is_callable().with_args().returns(root)
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

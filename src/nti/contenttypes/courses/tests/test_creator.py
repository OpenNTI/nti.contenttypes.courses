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

import os
import shutil
import tempfile

import fudge

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses.creator import make_directories
from nti.contenttypes.courses.creator import install_admin_level

from nti.externalization.interfaces import LocatedExternalDict

from nti.contenttypes.courses.tests import CourseLayerTest


class TestCreator(CourseLayerTest):

    @fudge.patch('nti.contenttypes.courses.creator.library_root')
    def test_install_admin_level(self, mock_lr):
        catalog = LocatedExternalDict()
        catalog.__name__ = 'Courses'

        tmp_dir = tempfile.mkdtemp()
        try:
            root = FilesystemBucket(name="root")
            root.absolute_path = tmp_dir
            mock_lr.is_callable().with_args().returns(root)
            # create courses place
            courses_path = os.path.join(tmp_dir, 'Courses')
            make_directories(courses_path)
            
            # writeout
            level = install_admin_level("Bleach", catalog=catalog)
            assert_that(level, is_not(none()))
            output = os.path.join(courses_path, 'Bleach')
            assert_that(level,
                        has_property('root', has_property('absolute_path', is_(output))))
            assert_that(os.path.exists(output), is_(True))
            
            # not writeout
            level = install_admin_level("Titan", catalog=catalog, writeout=False)
            assert_that(level, is_not(none()))
            output = os.path.join(courses_path, 'Titan')
            assert_that(level,
                        has_property('root', has_property('absolute_path', is_(output))))
            assert_that(os.path.exists(output), is_(False))
        finally:
            shutil.rmtree(tmp_dir)

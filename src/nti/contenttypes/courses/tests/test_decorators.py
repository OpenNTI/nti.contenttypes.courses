#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_entry
from hamcrest import assert_that

import fudge

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses.catalog import CourseCatalogFolder

from nti.contenttypes.courses.creator import create_course

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.externalization.externalization import to_external_object


class TestDecorators(CourseLayerTest):

    @fudge.patch('nti.contenttypes.courses.creator.library_root')
    def test_create_course(self, mock_lr):
        root = FilesystemBucket(name=u"root")
        root.absolute_path = '/tmp'
        mock_lr.is_callable().returns(root)

        catalog = CourseCatalogFolder()
        catalog.__name__ = u'Courses'
        course = create_course(u"Bleach", u"Shikai", catalog, writeout=True)
        ext_obj = to_external_object(course)
        assert_that(ext_obj, has_entry('AdminLevel', 'Bleach'))

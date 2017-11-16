#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that
from hamcrest import has_property

from nti.contenttypes.courses._bundle import created_content_package_bundle

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.generations.evolve35 import process_course

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
from nti.dataserver.tests.mock_dataserver import DataserverLayerTest


class TestEvolve35(DataserverLayerTest):

    @WithMockDSTrans
    def test_process_course(self):
        course = ContentCourseInstance()
        conn = mock_dataserver.current_transaction
        conn.add(course)
        entry = ICourseCatalogEntry(course)
        entry.ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-IAS_5912'
        created_content_package_bundle(course)
        bundle = course.ContentPackageBundle
        bundle.ntiid = u'tag:nextthought.com,2011-10:Bundle:CourseBundle-6432'

        assert_that(process_course(entry, course),
                    is_(True))

        assert_that(bundle,
                    has_property('ntiid', 'tag:nextthought.com,2011-10:NTI-Bundle:CourseBundle-IAS_5912'))

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import contains
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_inanyorder

from zope import component

from zope.intid.interfaces import IIntIds

from nti.testing.matchers import verifiably_provides

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.index import get_courses_catalog
from nti.contenttypes.courses.index import install_courses_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import get_course_tags
from nti.contenttypes.courses.utils import get_courses_for_tag
from nti.contenttypes.courses.utils import ProxyEnrollmentRecord

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
from nti.dataserver.tests.mock_dataserver import DataserverLayerTest

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.externalization.externalization import to_external_object

from nti.intid.common import addIntId


class TestCourse(DataserverLayerTest):

    def test_proxy(self):
        p = ProxyEnrollmentRecord()
        assert_that(p, verifiably_provides(ICourseInstanceEnrollmentRecord))


class TestTags(CourseLayerTest):

    @WithMockDSTrans
    def test_tags(self):
        ds_folder = self.ds.dataserver_folder
        install_courses_catalog(ds_folder)
        intids = component.queryUtility(IIntIds)
        catalog = get_courses_catalog()

        # Base/empty cases
        all_tags = get_course_tags()
        assert_that(all_tags, has_length(0))
        all_tags = get_course_tags(filter_str='entry3')
        assert_that(all_tags, has_length(0))
        courses = get_courses_for_tag('entry3_tag')
        assert_that(courses, has_length(0))

        # Create three courses, some with tags
        inst1 = ContentCourseInstance()
        entry1 = ICourseCatalogEntry(inst1)
        entry1.title = u'course1'
        ds_folder._p_jar.add(inst1)
        addIntId(inst1)
        catalog.index_doc(intids.getId(inst1), inst1)

        inst2 = ContentCourseInstance()
        entry2 = ICourseCatalogEntry(inst2)
        entry2.title = u'course2'
        inst2.tags = ('duplicate_tag',)
        ds_folder._p_jar.add(inst2)
        addIntId(inst2)
        catalog.index_doc(intids.getId(inst2), inst2)

        inst3 = ContentCourseInstance()
        entry3 = ICourseCatalogEntry(inst3)
        entry3.title = u'course3'
        inst3.tags = ('entry3_tag', 'DUPLICATE_TAG')
        ds_folder._p_jar.add(inst3)
        addIntId(inst3)
        catalog.index_doc(intids.getId(inst3), inst3)

        # Fetch tags
        all_tags = get_course_tags()
        assert_that(all_tags, has_length(2))
        assert_that(all_tags, contains_inanyorder('entry3_tag',
                                                  'duplicate_tag'))

        all_tags = get_course_tags(filter_str='entry3')
        assert_that(all_tags, has_length(1))
        assert_that(all_tags, contains('entry3_tag'))

        all_tags = get_course_tags(filter_str='ENTRY')
        assert_that(all_tags, has_length(1))
        assert_that(all_tags, contains('entry3_tag'))

        all_tags = get_course_tags(filter_str='taG')
        assert_that(all_tags, has_length(2))
        assert_that(all_tags, contains_inanyorder('entry3_tag',
                                                  'duplicate_tag'))

        all_tags = get_course_tags(filter_str='DNE')
        assert_that(all_tags, has_length(0))

        # Fetch courses
        def _get_titles(courses):
            return [ICourseCatalogEntry(x).title for x in courses]

        courses = get_courses_for_tag('entry3_tag')
        assert_that(courses, has_length(1))
        assert_that(_get_titles(courses), contains('course3'))

        courses = get_courses_for_tag('duplicate_tag')
        assert_that(courses, has_length(2))
        assert_that(_get_titles(courses), contains_inanyorder('course2',
                                                              'course3'))

        courses = get_courses_for_tag('DUPLICATE_TAG')
        assert_that(courses, has_length(2))
        assert_that(_get_titles(courses), contains_inanyorder('course2',
                                                              'course3'))

        # Unindex third course
        catalog.unindex_doc(intids.getId(inst3))

        all_tags = get_course_tags()
        assert_that(all_tags, has_length(1))
        assert_that(all_tags, contains('duplicate_tag'))

        all_tags = get_course_tags(filter_str='entry3')
        assert_that(all_tags, has_length(0))

        courses = get_courses_for_tag('entry3_tag')
        assert_that(courses, has_length(0))

        courses = get_courses_for_tag('duplicate_tag')
        assert_that(courses, has_length(1))
        assert_that(_get_titles(courses), contains('course2'))

        # No courses with tags
        catalog.unindex_doc(intids.getId(inst2))

        all_tags = get_course_tags()
        assert_that(all_tags, has_length(0))

        all_tags = get_course_tags(filter_str='entry3')
        assert_that(all_tags, has_length(0))

        courses = get_courses_for_tag('entry3_tag')
        assert_that(courses, has_length(0))

        courses = get_courses_for_tag('duplicate_tag')
        assert_that(courses, has_length(0))

        # External tags
        ext_obj = to_external_object(inst3)
        assert_that(ext_obj, has_entry('tags',
                                       contains_inanyorder('entry3_tag',
                                                           'DUPLICATE_TAG')))

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

import fudge

from zope import component

from zope.intid.interfaces import IIntIds

from nti.testing.matchers import verifiably_provides

from nti.contentfragments.interfaces import IPlainTextContentFragment

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.index import get_courses_catalog
from nti.contenttypes.courses.index import get_enrollment_catalog
from nti.contenttypes.courses.index import install_courses_catalog
from nti.contenttypes.courses.index import install_enrollment_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import get_course_tags
from nti.contenttypes.courses.utils import index_course_roles
from nti.contenttypes.courses.utils import get_courses_for_tag
from nti.contenttypes.courses.utils import ProxyEnrollmentRecord
from nti.contenttypes.courses.utils import get_context_enrollment_records

from nti.dataserver.users import User

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
        courses = get_courses_for_tag('entry3 tag')
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
        entry2.tags = (IPlainTextContentFragment(u'duplicate_tag'),)
        ds_folder._p_jar.add(inst2)
        addIntId(inst2)
        catalog.index_doc(intids.getId(inst2), inst2)

        inst3 = ContentCourseInstance()
        entry3 = ICourseCatalogEntry(inst3)
        entry3.title = u'course3'
        entry3.tags = (IPlainTextContentFragment(u'entry3 tag'),
                       IPlainTextContentFragment(u'DUPLICATE_TAG'))
        ds_folder._p_jar.add(inst3)
        addIntId(inst3)
        catalog.index_doc(intids.getId(inst3), inst3)

        # Fetch tags
        all_tags = get_course_tags()
        assert_that(all_tags, has_length(2))
        assert_that(all_tags, contains_inanyorder(u'entry3 tag',
                                                  u'duplicate_tag'))

        all_tags = get_course_tags(filter_str=u'entry3')
        assert_that(all_tags, has_length(1))
        assert_that(all_tags, contains(u'entry3 tag'))

        all_tags = get_course_tags(filter_str=u'ENTRY')
        assert_that(all_tags, has_length(1))
        assert_that(all_tags, contains(u'entry3 tag'))

        all_tags = get_course_tags(filter_str=u'taG')
        assert_that(all_tags, has_length(2))
        assert_that(all_tags, contains_inanyorder(u'entry3 tag',
                                                  u'duplicate_tag'))

        all_tags = get_course_tags(filter_str=u'DNE')
        assert_that(all_tags, has_length(0))

        # Fetch courses
        def _get_titles(courses):
            return [ICourseCatalogEntry(x).title for x in courses]

        courses = get_courses_for_tag(u'entry3 tag')
        assert_that(courses, has_length(1))
        assert_that(_get_titles(courses), contains('course3'))

        courses = get_courses_for_tag(u'duplicate_tag')
        assert_that(courses, has_length(2))
        assert_that(_get_titles(courses), contains_inanyorder('course2',
                                                              'course3'))

        courses = get_courses_for_tag(u'DUPLICATE_TAG')
        assert_that(courses, has_length(2))
        assert_that(_get_titles(courses), contains_inanyorder('course2',
                                                              'course3'))

        # Unindex third course
        catalog.unindex_doc(intids.getId(inst3))

        all_tags = get_course_tags()
        assert_that(all_tags, has_length(1))
        assert_that(all_tags, contains(u'duplicate_tag'))

        all_tags = get_course_tags(filter_str='entry3')
        assert_that(all_tags, has_length(0))

        courses = get_courses_for_tag(u'entry3 tag')
        assert_that(courses, has_length(0))

        courses = get_courses_for_tag(u'duplicate_tag')
        assert_that(courses, has_length(1))
        assert_that(_get_titles(courses), contains('course2'))

        # No courses with tags
        catalog.unindex_doc(intids.getId(inst2))

        all_tags = get_course_tags()
        assert_that(all_tags, has_length(0))

        all_tags = get_course_tags(filter_str=u'entry3')
        assert_that(all_tags, has_length(0))

        courses = get_courses_for_tag(u'entry3 tag')
        assert_that(courses, has_length(0))

        courses = get_courses_for_tag(u'duplicate_tag')
        assert_that(courses, has_length(0))

        # External tags
        ext_obj = to_external_object(entry3)
        assert_that(ext_obj, has_entry('tags',
                                       contains_inanyorder(u'entry3 tag',
                                                           u'DUPLICATE_TAG')))


class TestContextEnrollments(CourseLayerTest):

    @WithMockDSTrans
    @fudge.patch('nti.contenttypes.courses.utils.is_admin_or_site_admin')
    def test_context_enrollments(self, fudge_admin):
        ds_folder = self.ds.dataserver_folder
        install_enrollment_catalog(ds_folder)
        install_courses_catalog(ds_folder)
        intids = component.queryUtility(IIntIds)
        enrollment_catalog = get_enrollment_catalog()

        # Base/empty cases
        admin_user = User.create_user(username='sjohnson@nextthought.com')
        instructor_user = User.create_user(username='instructor_user')
        student_user = User.create_user(username='student_user')
        fudge_admin.is_callable().returns(True)
        records = get_context_enrollment_records(None, None)
        assert_that(records, has_length(0))
        records = get_context_enrollment_records(student_user, None)
        assert_that(records, has_length(0))
        records = get_context_enrollment_records(student_user, admin_user)
        assert_that(records, has_length(0))
        fudge_admin.is_callable().returns(False)
        records = get_context_enrollment_records(student_user, instructor_user)
        assert_that(records, has_length(0))

        # Create two courses, one with instructor, one without.
        inst1 = ContentCourseInstance()
        entry1 = ICourseCatalogEntry(inst1)
        entry1.title = u'course1'
        ds_folder._p_jar.add(inst1)
        addIntId(inst1)
        inst1.instructors = (instructor_user,)
        index_course_roles(inst1, catalog=enrollment_catalog, intids=intids)

        inst2 = ContentCourseInstance()
        entry2 = ICourseCatalogEntry(inst2)
        entry2.title = u'course2'
        ds_folder._p_jar.add(inst2)
        addIntId(inst2)

        # One course
        enrollments = ICourseEnrollmentManager(inst1)
        record = enrollments.enroll(student_user)
        enrollment_catalog.index_doc(intids.getId(record), record)

        fudge_admin.is_callable().returns(True)
        records = get_context_enrollment_records(student_user, admin_user)
        assert_that(records, has_length(1))
        assert_that(records, contains(record))
        fudge_admin.is_callable().returns(False)
        records = get_context_enrollment_records(student_user, instructor_user)
        assert_that(records, has_length(1))
        assert_that(records, contains(record))
        
        records = get_context_enrollment_records(student_user, student_user)
        assert_that(records, has_length(1))
        assert_that(records, contains(record))

        # Two courses
        enrollments = ICourseEnrollmentManager(inst2)
        record2 = enrollments.enroll(student_user)
        enrollment_catalog.index_doc(intids.getId(record2), record2)

        fudge_admin.is_callable().returns(True)
        records = get_context_enrollment_records(student_user, admin_user)
        assert_that(records, has_length(2))
        assert_that(records, contains_inanyorder(record, record2))
        fudge_admin.is_callable().returns(False)
        records = get_context_enrollment_records(student_user, instructor_user)
        assert_that(records, has_length(1))
        assert_that(records, contains(record))
        
        records = get_context_enrollment_records(student_user, student_user)
        assert_that(records, has_length(2))
        assert_that(records, contains_inanyorder(record, record2))

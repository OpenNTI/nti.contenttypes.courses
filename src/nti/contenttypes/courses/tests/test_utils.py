#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import contains
from hamcrest import has_items
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import contains_inanyorder

import fudge

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.testing.matchers import verifiably_provides

from nti.contentfragments.interfaces import IPlainTextContentFragment

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.index import get_courses_catalog
from nti.contenttypes.courses.index import get_enrollment_catalog
from nti.contenttypes.courses.index import install_courses_catalog
from nti.contenttypes.courses.index import install_enrollment_catalog

from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.interfaces import IDeletedCourse
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntryFilterUtility
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import get_editors
from nti.contenttypes.courses.utils import get_instructors
from nti.contenttypes.courses.utils import get_course_tags
from nti.contenttypes.courses.utils import index_course_roles
from nti.contenttypes.courses.utils import get_courses_for_tag
from nti.contenttypes.courses.utils import ProxyEnrollmentRecord
from nti.contenttypes.courses.utils import get_instructed_courses
from nti.contenttypes.courses.utils import get_enrollment_records
from nti.contenttypes.courses.utils import get_entry_intids_for_title
from nti.contenttypes.courses.utils import get_all_site_course_intids
from nti.contenttypes.courses.utils import entry_intids_to_course_intids
from nti.contenttypes.courses.utils import course_intids_to_entry_intids
from nti.contenttypes.courses.utils import get_context_enrollment_records
from nti.contenttypes.courses.utils import get_instructed_and_edited_courses
from nti.contenttypes.courses.utils import get_site_course_admin_intids_for_user

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


class TestEntryFilters(CourseLayerTest):

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
        ds_folder._p_jar.add(entry1)
        addIntId(entry1)
        catalog.index_doc(intids.getId(inst1), inst1)
        catalog.index_doc(intids.getId(entry1), entry1)

        inst2 = ContentCourseInstance()
        entry2 = ICourseCatalogEntry(inst2)
        entry2.title = u'course2'
        entry2.tags = (IPlainTextContentFragment(u'duplicate_tag'),)
        ds_folder._p_jar.add(inst2)
        addIntId(inst2)
        ds_folder._p_jar.add(entry2)
        addIntId(entry2)
        catalog.index_doc(intids.getId(inst2), inst2)
        catalog.index_doc(intids.getId(entry2), entry2)

        inst3 = ContentCourseInstance()
        entry3 = ICourseCatalogEntry(inst3)
        entry3.title = u'course3'
        entry3.tags = (IPlainTextContentFragment(u'entry3 tag'),
                       IPlainTextContentFragment(u'DUPLICATE_TAG'))
        ds_folder._p_jar.add(inst3)
        addIntId(inst3)
        ds_folder._p_jar.add(entry3)
        addIntId(entry3)
        catalog.index_doc(intids.getId(inst3), inst3)
        catalog.index_doc(intids.getId(entry3), entry3)

        # Fetch tags
        all_tags = get_course_tags()
        assert_that(all_tags, has_length(2))
        assert_that(all_tags, has_entries(u'entry3 tag', 1,
                                          u'duplicate_tag', 2))

        all_tags = get_course_tags(filter_str=u'entry3')
        assert_that(all_tags, has_length(1))
        assert_that(all_tags, contains(u'entry3 tag'))

        all_tags = get_course_tags(filter_str=u'ENTRY')
        assert_that(all_tags, has_length(1))
        assert_that(all_tags, contains(u'entry3 tag'))

        all_tags = get_course_tags(filter_str=u'taG')
        assert_that(all_tags, has_length(2))
        assert_that(all_tags, has_entries(u'entry3 tag', 1,
                                          u'duplicate_tag', 2))

        # Deleted course
        interface.alsoProvides(inst3, IDeletedCourse)
        catalog.index_doc(intids.getId(inst3), inst3)
        catalog.index_doc(intids.getId(entry3), entry3)
        all_tags = get_course_tags()
        assert_that(all_tags, has_length(1))
        assert_that(all_tags, has_entries(u'duplicate_tag', 1))

        interface.noLongerProvides(inst3, IDeletedCourse)
        catalog.index_doc(intids.getId(inst3), inst3)
        catalog.index_doc(intids.getId(entry3), entry3)
        interface.alsoProvides(entry2, INonPublicCourseInstance)
        catalog.index_doc(intids.getId(entry2), entry2)
        all_tags = get_course_tags()
        assert_that(all_tags, has_length(2))
        assert_that(all_tags, has_entries(u'entry3 tag', 1,
                                          u'duplicate_tag', 1))
        interface.noLongerProvides(entry2, INonPublicCourseInstance)
        catalog.index_doc(intids.getId(entry2), entry2)

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

        # Remove tag from course and it does not come back
        # Indexing the course does not affect anything
        catalog.index_doc(intids.getId(inst3), inst3)
        entry3.tags = (IPlainTextContentFragment(u'entry3 tag'),)
        catalog.index_doc(intids.getId(entry3), entry3)
        courses = get_courses_for_tag(u'DUPLICATE_TAG')
        assert_that(courses, has_length(1))
        assert_that(_get_titles(courses), contains_inanyorder('course2'))

        # Unindex third course
        catalog.unindex_doc(intids.getId(entry3))

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
        catalog.unindex_doc(intids.getId(entry2))

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
                                       contains_inanyorder(u'entry3 tag',)))

    @WithMockDSTrans
    def test_titles(self):
        ds_folder = self.ds.dataserver_folder
        install_courses_catalog(ds_folder)
        intids = component.queryUtility(IIntIds)
        catalog = get_courses_catalog()

        # Base/empty cases
        result = get_entry_intids_for_title("title")
        assert_that(result, has_length(0))

        # Create three courses, some with tags
        inst1 = ContentCourseInstance()
        entry1 = ICourseCatalogEntry(inst1)
        entry1.title = u'course one'
        ds_folder._p_jar.add(inst1)
        addIntId(inst1)
        ds_folder._p_jar.add(entry1)
        addIntId(entry1)
        catalog.index_doc(intids.getId(entry1), entry1)

        inst2 = ContentCourseInstance()
        entry2 = ICourseCatalogEntry(inst2)
        entry2.title = u'course2'
        ds_folder._p_jar.add(inst2)
        addIntId(inst2)
        ds_folder._p_jar.add(entry2)
        addIntId(entry2)
        catalog.index_doc(intids.getId(entry2), entry2)

        inst3 = ContentCourseInstance()
        entry3 = ICourseCatalogEntry(inst3)
        entry3.title = u'COURSE three'
        ds_folder._p_jar.add(inst3)
        addIntId(inst3)
        ds_folder._p_jar.add(entry3)
        addIntId(entry3)
        catalog.index_doc(intids.getId(entry3), entry3)

        # Fetch entries
        def _get_entries(rs):
            return [intids.getObject(x) for x in rs]

        result = get_entry_intids_for_title(u'three')
        assert_that(result, has_length(1))
        assert_that(_get_entries(result), contains(entry3))

        result = get_entry_intids_for_title(u'couRSE*')
        assert_that(result, has_length(3))
        assert_that(_get_entries(result),
                     contains_inanyorder(entry1, entry2, entry3))

        catalog.index_doc(intids.getId(entry3), entry3)
        result = get_entry_intids_for_title(u'course three')
        assert_that(result, has_length(1))
        assert_that(_get_entries(result), contains_inanyorder(entry3))

        # Cannot suffix search
#         result = get_entry_intids_for_title([u'*urse*'])
#         assert_that(result, has_length(3))
#         assert_that(_get_entries(result),
#                      contains_inanyorder(entry1, entry2, entry3))

        result = get_entry_intids_for_title(u'cour*')
        assert_that(result, has_length(3))
        assert_that(_get_entries(result),
                     contains_inanyorder(entry1, entry2, entry3))

        filter_util = component.getUtility(ICourseCatalogEntryFilterUtility)
        result = filter_util.get_entry_intids_for_filters([u'one', u'thre*'])
        assert_that(result, has_length(2))
        assert_that(_get_entries(result),
                     contains_inanyorder(entry1, entry3))

        # auto glob
        filter_util = component.getUtility(ICourseCatalogEntryFilterUtility)
        result = filter_util.get_entry_intids_for_filters([u'one', u'thre'])
        assert_that(result, has_length(2))
        assert_that(_get_entries(result),
                     contains_inanyorder(entry1, entry3))

        result = filter_util.get_entry_intids_for_filters([u'one', u'thre*'], union=False)
        assert_that(result, has_length(0))

        # Unindex third course
        catalog.unindex_doc(intids.getId(entry3))
        result = filter_util.get_entry_intids_for_filters([u'one', u'thre*'])
        assert_that(result, has_length(1))
        assert_that(_get_entries(result),
                     contains_inanyorder(entry1))

        # Invalid search
        result = filter_util.get_entry_intids_for_filters(u' ')
        assert_that(result, has_length(0))


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
        editor_user = User.create_user(username='editor_user')
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
        entry1.ntiid = u'ntiid1'
        ds_folder._p_jar.add(inst1)
        addIntId(inst1)
        inst1.instructors = (instructor_user,)
        inst1.editors = (editor_user,)
        prm = IPrincipalRoleManager(inst1)
        prm.assignRoleToPrincipal(RID_CONTENT_EDITOR, editor_user.username)
        index_course_roles(inst1, catalog=enrollment_catalog, intids=intids)

        inst2 = ContentCourseInstance()
        entry2 = ICourseCatalogEntry(inst2)
        entry2.title = u'course2'
        entry2.ntiid = u'ntiid2'
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

        # Validate inst catalog queries (including if a user is an editor in
        # one course, but an instructor in another).
        inst2.instructors = (editor_user,)
        index_course_roles(inst2, catalog=enrollment_catalog, intids=intids)
        instructed_courses = get_instructed_courses(instructor_user)
        assert_that(instructed_courses, contains(inst1))
        instructed_courses = get_instructed_courses(editor_user)
        assert_that(instructed_courses, contains(inst2))
        instructed_courses = get_instructed_courses(student_user)
        assert_that(instructed_courses, has_length(0))

        instructed_courses = get_instructed_and_edited_courses(instructor_user)
        assert_that(instructed_courses, contains(inst1))
        instructed_courses = get_instructed_and_edited_courses(editor_user)
        assert_that(instructed_courses, contains_inanyorder(inst1, inst2))
        instructed_courses = get_instructed_and_edited_courses(student_user)
        assert_that(instructed_courses, has_length(0))

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
    def test_get_enrollment_records(self):
        ds_folder = self.ds.dataserver_folder
        intids = component.queryUtility(IIntIds)
        enrollment_catalog = get_enrollment_catalog()

        user1 = User.create_user(username=u'user001')
        user2 = User.create_user(username=u'user002')
        user3 = User.create_user(username=u'user003')

        result = get_enrollment_records(usernames=())
        assert_that(result, has_length(0))
        result = get_enrollment_records(usernames=('user001',))
        assert_that(result, has_length(0))
        result = get_enrollment_records(usernames=('user001', 'user002'))
        assert_that(result, has_length(0))

        course1, entry1 = self._add_course(u'course1', ds_folder)
        course2, entry2 = self._add_course(u'course2', ds_folder)
        course3, entry3 = self._add_course(u'course3', ds_folder)

        record11 = self._enroll(user1, course1, enrollment_catalog, intids)
        record12 = self._enroll(user1, course2, enrollment_catalog, intids)
        record22 = self._enroll(user2, course2, enrollment_catalog, intids)

        # return all enrollments in the current site.
        result = get_enrollment_records()
        assert_that(result, has_length(3))

        # return user's all enrollments in the current site.
        result = get_enrollment_records(usernames=('user001',))
        assert_that(result, contains_inanyorder(record11, record12))
        result = get_enrollment_records(usernames=('user002',))
        assert_that(result, contains_inanyorder(record22))
        result = get_enrollment_records(usernames=('user003',))
        assert_that(result, has_length(0))

        result = get_enrollment_records(usernames=('user001', 'user002'))
        assert_that(result, contains_inanyorder(record11, record12, record22))
        result = get_enrollment_records(usernames=('user001', 'user002', 'user003'))
        assert_that(result, contains_inanyorder(record11, record12, record22))

        # return user's enrollments for specified courses in the current site.
        result = get_enrollment_records(usernames=('user001',), entry_ntiids=(entry1.ntiid,))
        assert_that(result, contains_inanyorder(record11))
        result = get_enrollment_records(usernames=('user001',), entry_ntiids=(entry2.ntiid,))
        assert_that(result, contains_inanyorder(record12))
        result = get_enrollment_records(usernames=('user001',), entry_ntiids=(entry1.ntiid, entry2.ntiid))
        assert_that(result, contains_inanyorder(record11, record12))
        result = get_enrollment_records(usernames=('user001',), entry_ntiids=(entry3.ntiid,))
        assert_that(result, has_length(0))

        result = get_enrollment_records(usernames=('user001', 'user003'), entry_ntiids=(entry1.ntiid, entry2.ntiid))
        assert_that(result, contains_inanyorder(record11, record12))
        result = get_enrollment_records(usernames=('user001','user002'), entry_ntiids=(entry1.ntiid, entry2.ntiid))
        assert_that(result, contains_inanyorder(record11, record12, record22))

        # return course's all enrollments in the current site.
        assert_that(get_enrollment_records(entry_ntiids=(entry1.ntiid,)), contains_inanyorder(record11))
        assert_that(get_enrollment_records(entry_ntiids=(entry2.ntiid,)), contains_inanyorder(record12, record22))
        assert_that(get_enrollment_records(entry_ntiids=(entry3.ntiid,)), has_length(0))

        assert_that(get_enrollment_records(entry_ntiids=(entry1.ntiid, entry2.ntiid)), contains_inanyorder(record11, record12, record22))
        assert_that(get_enrollment_records(entry_ntiids=(entry1.ntiid, entry3.ntiid)), contains_inanyorder(record11))

        # sites
        assert_that(get_enrollment_records(sites=(u'xxx',)), has_length(0))


class TestUtils(CourseLayerTest):

    def _get_courses_catalog(self):
        if getattr(self, '_courses_catalog', None) is None:
            ds_folder = self.ds.dataserver_folder
            self._courses_catalog = install_courses_catalog(ds_folder)
        return self._courses_catalog

    def _create_course(self, title=u'course1', ntiid=u'ntiid1', instructors=(), editors=()):
        ds_folder = self.ds.dataserver_folder
        intids = component.queryUtility(IIntIds)
        courses_catalog = install_courses_catalog(ds_folder)

        inst = ContentCourseInstance()
        inst.__name__ = title
        entry = ICourseCatalogEntry(inst)
        entry.title = title
        entry.ntiid = ntiid
        ds_folder._p_jar.add(inst)
        addIntId(inst)
        addIntId(entry)

        inst.instructors = [IPrincipal(x) for x in instructors];

        prm = IPrincipalRoleManager(inst)
        for editor in editors:
            prm.assignRoleToPrincipal(RID_CONTENT_EDITOR, editor.username)

        doc_id = intids.getId(inst)
        entry_id = intids.getId(entry)
        courses_catalog.index_doc(doc_id, inst)
        courses_catalog.index_doc(entry_id, entry)
        return (doc_id, inst)

    @WithMockDSTrans
    def test_intids(self):
        course1_intid, course1 = self._create_course()
        entry1 = ICourseCatalogEntry(course1)
        course2_intid, course2 = self._create_course()
        entry2 = ICourseCatalogEntry(course2)
        course3_intid, course3 = self._create_course()
        entry3 = ICourseCatalogEntry(course3)

        intids = component.getUtility(IIntIds)
        entry1_intid = intids.getId(entry1)
        entry2_intid = intids.getId(entry2)
        entry3_intid = intids.getId(entry3)
        rs = entry_intids_to_course_intids(())
        assert_that(rs, has_length(0))

        rs = entry_intids_to_course_intids((course1_intid,))
        assert_that(rs, has_length(0))
        rs = entry_intids_to_course_intids((entry1_intid,))
        assert_that(rs, contains(course1_intid))
        rs = entry_intids_to_course_intids((entry3_intid,))
        assert_that(rs, contains(course3_intid))
        rs = entry_intids_to_course_intids((entry3_intid, entry1_intid, entry2_intid))
        assert_that(rs, contains_inanyorder(course3_intid, course2_intid, course1_intid))

        rs = course_intids_to_entry_intids((entry1_intid,))
        assert_that(rs, has_length(0))
        rs = course_intids_to_entry_intids((course1_intid,))
        assert_that(rs, contains(entry1_intid))
        rs = course_intids_to_entry_intids((course2_intid,))
        assert_that(rs, contains(entry2_intid))
        rs = course_intids_to_entry_intids((course1_intid, course3_intid, course2_intid))
        assert_that(rs, contains_inanyorder(entry3_intid, entry2_intid, entry1_intid))

    @WithMockDSTrans
    @fudge.patch('nti.contenttypes.courses.index.get_course_site',
                 'nti.contenttypes.courses.utils.get_host_site',
                 'nti.contenttypes.courses.utils.is_site_admin')
    def test_instructors_editors(self, mock_course_site, mock_host_site, mock_site_admin):
        ds_folder = self.ds.dataserver_folder
        courses_catalog = install_courses_catalog(ds_folder)
        mock_course_site.is_callable().returns('alpha.dev')
        mock_site_admin.is_callable().returns(False)
        mock_host_site.is_callable().returns(object())

        instructor_user1 = User.create_user(username='instructor_user1')
        instructor_user2 = User.create_user(username='instructor_user2')
        instructor_user3 = User.create_user(username='instructor_user3')
        editor_user1 = User.create_user(username='editor_user1')
        editor_user2 = User.create_user(username='editor_user2')
        non_user = User.create_user(username='non_user')

        # Empty cases
        result = get_instructors(site='alpha.dev')
        assert_that(result, has_length(0))
        result = get_editors(site='alpha.dev')
        assert_that(result, has_length(0))

        # course with instructors and editors
        course1 = self._create_course(instructors=(instructor_user1, instructor_user2),
                                      editors=(editor_user1,),
                                      ntiid=u'ntiid1')

        result = get_instructors(site='alpha.dev')
        assert_that(result, has_length(2))
        assert_that([x.username for x in result],
                    has_items('instructor_user1', 'instructor_user2'))
        result = get_editors(site='alpha.dev')
        assert_that(result, has_length(1))
        assert_that([x.username for x in result],
                    has_items('editor_user1'))

        # course without editors
        course2 = self._create_course(instructors=(instructor_user3,),
                                      ntiid=u'ntiid2')
        result = get_instructors(site='alpha.dev')
        assert_that(result, has_length(3))
        assert_that([x.username for x in result],
                    has_items('instructor_user1', 'instructor_user2', 'instructor_user3'))
        result = get_editors(site='alpha.dev')
        assert_that(result, has_length(1))
        assert_that([x.username for x in result], has_items('editor_user1'))

        # course without instructors
        course3 = self._create_course(editors=(editor_user2,),
                                      ntiid=u'ntiid3')
        result = get_instructors(site='alpha.dev')
        assert_that(result, has_length(3))
        assert_that([x.username for x in result],
                    has_items('instructor_user1', 'instructor_user2', 'instructor_user3'))
        result = get_editors(site='alpha.dev')
        assert_that(result, has_length(2))
        assert_that([x.username for x in result],
                    has_items('editor_user1', 'editor_user2'))

        # course without instructors and editors.
        course4 = self._create_course(ntiid=u'ntiid4')
        result = get_instructors(site='alpha.dev')
        assert_that(result, has_length(3))
        assert_that([x.username for x in result],
                    has_items('instructor_user1', 'instructor_user2', 'instructor_user3'))
        result = get_editors(site='alpha.dev')
        assert_that(result, has_length(2))
        assert_that([x.username for x in result],
                    has_items('editor_user1', 'editor_user2'))

        result = get_instructors(site='alpha.dev', excludedCourse=course1[1])
        assert_that(result, has_length(1))
        assert_that([x.username for x in result], has_items('instructor_user3'))
        result = get_editors(site='alpha.dev', excludedCourse=course1[1])
        assert_that(result, has_length(1))
        assert_that([x.username for x in result], has_items('editor_user2'))

        result = get_all_site_course_intids(site='alpha.dev')
        assert_that(result, has_length(4))

        result = get_site_course_admin_intids_for_user(non_user, site='alpha.dev')
        assert_that(result, has_length(0))

        result = get_site_course_admin_intids_for_user(instructor_user1, site='alpha.dev')
        assert_that(result, has_length(1))

        result = get_site_course_admin_intids_for_user(editor_user1, site='alpha.dev')
        assert_that(result, has_length(1))

        mock_site_admin.is_callable().returns(True)
        result = get_site_course_admin_intids_for_user(non_user, site='alpha.dev')
        assert_that(result, has_length(4))

        result = get_site_course_admin_intids_for_user(instructor_user1, site='alpha.dev')
        assert_that(result, has_length(4))

        courses_catalog.unindex_doc(course4[0])
        assert_that(get_instructors(site='alpha.dev'), has_length(3))
        assert_that(get_editors(site='alpha.dev'), has_length(2))

        courses_catalog.unindex_doc(course3[0])
        assert_that(get_instructors(site='alpha.dev'), has_length(3))
        assert_that(get_editors(site='alpha.dev'), has_length(1))

        courses_catalog.unindex_doc(course2[0])
        assert_that(get_instructors(site='alpha.dev'), has_length(2))
        assert_that(get_editors(site='alpha.dev'), has_length(1))

        courses_catalog.unindex_doc(course1[0])
        assert_that(get_instructors(site='alpha.dev'), has_length(0))
        assert_that(get_editors(site='alpha.dev'), has_length(0))

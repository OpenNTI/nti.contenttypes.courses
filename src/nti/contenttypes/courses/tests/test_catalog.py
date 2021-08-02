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
from hamcrest import not_none
from hamcrest import has_items
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

import isodate

from zope.location.interfaces import ILocation

from nti.contenttypes.courses.catalog import CourseCatalogEntry
from nti.contenttypes.courses.catalog import CourseCatalogFolder
from nti.contenttypes.courses.catalog import GlobalCourseCatalog

from nti.contenttypes.courses.courses import CourseSeatLimit
from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel

from nti.contenttypes.courses.legacy_catalog import CourseCatalogLegacyEntry
from nti.contenttypes.courses.legacy_catalog import _CourseSubInstanceCatalogLegacyEntry

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IGlobalCourseCatalog
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.contenttypes.courses.utils import _used_seats
from nti.contenttypes.courses.utils import can_user_enroll

from nti.contenttypes.courses.tests import MockPrincipal
from nti.contenttypes.courses.tests import CourseLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.externalization.externalization import to_external_object

from nti.externalization.internalization import update_from_external_object


class TestCatalog(CourseLayerTest):

    def test_global_catalog(self):
        assert_that(GlobalCourseCatalog(),
                    validly_provides(IGlobalCourseCatalog))

    def test_catalog_implements(self):
        assert_that(CourseCatalogFolder(),
                    validly_provides(ICourseCatalog))

    def test_entry_implements(self):
        assert_that(CourseCatalogEntry(),
                    verifiably_provides(ICourseCatalogEntry))
        assert_that(CourseCatalogEntry(),
                    validly_provides(ILocation))

        assert_that(_CourseSubInstanceCatalogLegacyEntry(),
                    validly_provides(ILocation))

    def test_entry_timestamps(self):
        cce = CourseCatalogEntry()
        assert_that(cce, has_property('lastModified', 0))
        assert_that(cce, has_property('createdTime', 0))

        lcce = _CourseSubInstanceCatalogLegacyEntry()
        assert_that(lcce, has_property('lastModified', 0))
        assert_that(lcce, has_property('createdTime', 0))

        lcce._next_entry = cce
        assert_that(lcce, has_property('lastModified', 0))
        assert_that(lcce, has_property('createdTime', 0))

        cce.lastModified = cce.createdTime = 42

        assert_that(cce, has_property('lastModified', 42))
        assert_that(cce, has_property('createdTime', 42))

        # but they don't propagate down
        assert_that(lcce, has_property('lastModified', 0))
        assert_that(lcce, has_property('createdTime', 0))

    def test_preview(self):
        cce = CourseCatalogLegacyEntry()
        assert_that(cce, has_property('Preview', is_(False)))

        lcce = _CourseSubInstanceCatalogLegacyEntry()
        assert_that(lcce, has_property('Preview', is_(False)))

        lcce._next_entry = cce
        assert_that(lcce, has_property('Preview', is_(False)))

        cce.Preview = True

        assert_that(lcce, has_property('Preview', is_(True)))

        lcce.StartDate = isodate.parse_datetime('2001-01-01T00:00')
        assert_that(lcce, has_property('Preview', is_(False)))

        lcce.Preview = True
        assert_that(lcce, has_property('Preview', is_(True)))

        del lcce.Preview
        assert_that(lcce, has_property('Preview', is_(False)))

        del lcce.StartDate
        assert_that(lcce, has_property('Preview', is_(True))) 

    @WithMockDSTrans
    def test_ext(self):
        catalog = CourseCatalogFolder()
        catalog._setitemf('level1', CourseAdministrativeLevel())
        catalog._setitemf('level2', CourseAdministrativeLevel())
        ext_obj = to_external_object(catalog)
        assert_that(ext_obj,
                    has_entries('Last Modified', not_none(),
                                'CreatedTime', not_none(),
                                'MimeType', 'application/vnd.nextthought.courses.coursecatalogfolder',
                                'anonymously_accessible', False))
        assert_that(ext_obj,
                    does_not(has_items('level1', 'level2')))
        
    @WithMockDSTrans
    def test_entry_ext(self):
        prin1 = MockPrincipal()
        self.ds.root[prin1.id] = prin1
        admin = CourseAdministrativeLevel()
        self.ds.root[u'admin'] = admin
        
        course = ContentCourseInstance()
        admin['course'] = course
        course_enrollment_manager = ICourseEnrollmentManager(course)
        cce = ICourseCatalogEntry(course)
        cce.ProviderUniqueID = u'1234'
        cce.title = u'course title'
        cce.__parent__ = course
        cce_ext = to_external_object(cce)
        
        # Subinstance inherits from parent
        subinst = ContentCourseSubInstance()
        subinst_enrollment_manager = ICourseEnrollmentManager(subinst)
        course.SubInstances[u'child'] = subinst
        sub_entry = ICourseCatalogEntry(subinst)
        assert_that(sub_entry.seat_limit, none())
        
        # Set on parent course
        seat_limit_ext = {'MimeType': CourseSeatLimit.mime_type,
                          'max_seats': 1}
        source_ext_obj = {}
        source_ext_obj['MimeType'] = cce_ext['MimeType']
        source_ext_obj['seat_limit'] = seat_limit_ext
        
        ext_obj = dict(source_ext_obj)
        update_from_external_object(cce, ext_obj, require_updater=True)
        
        cce_ext = to_external_object(cce)
        seat_limit_ext = cce_ext.get('seat_limit')
        assert_that(seat_limit_ext, has_entries('hard_limit', True,
                                                'max_seats', 1,
                                                'used_seats', 0))
        assert_that(sub_entry.seat_limit, is_(cce.seat_limit))
        
        # Enroll
        course_enrollment_manager.enroll(prin1)
        assert_that(_used_seats(cce.seat_limit), is_(1))
        assert_that(_used_seats(sub_entry.seat_limit), is_(0))
        assert_that(can_user_enroll(cce.seat_limit), is_(False))
        assert_that(can_user_enroll(sub_entry.seat_limit), is_(True))
        
        course_enrollment_manager.drop(prin1)
        subinst_enrollment_manager.enroll(prin1)
        assert_that(_used_seats(cce.seat_limit), is_(0))
        assert_that(_used_seats(sub_entry.seat_limit), is_(1))
        assert_that(can_user_enroll(cce.seat_limit), is_(True))
        assert_that(can_user_enroll(sub_entry.seat_limit), is_(False))
        
        course_enrollment_manager.enroll(prin1)
        assert_that(_used_seats(cce.seat_limit), is_(1))
        assert_that(_used_seats(sub_entry.seat_limit), is_(1))
        assert_that(can_user_enroll(cce.seat_limit), is_(False))
        assert_that(can_user_enroll(sub_entry.seat_limit), is_(False))

        # Remove limit
        ext_obj = dict(source_ext_obj)
        ext_obj['seat_limit']['max_seats'] = None
        update_from_external_object(cce, ext_obj, require_updater=True)
        
        cce_ext = to_external_object(cce)
        seat_limit_ext = cce_ext.get('seat_limit')
        assert_that(seat_limit_ext, has_entries('hard_limit', True,
                                                'max_seats', none(),
                                                'used_seats', 0))
        
        assert_that(sub_entry.seat_limit, is_(cce.seat_limit))
        cce_ext = to_external_object(sub_entry)
        seat_limit_ext = cce_ext.get('seat_limit')
        assert_that(seat_limit_ext, has_entries('hard_limit', True,
                                                'max_seats', none(),
                                                'used_seats', 0))

        # Update sub entry diverges
        seat_limit_ext2 = {'MimeType': CourseSeatLimit.mime_type,
                           'max_seats': 10}
        ext_obj = dict(source_ext_obj)
        ext_obj['seat_limit'] = seat_limit_ext2
        update_from_external_object(sub_entry, ext_obj, require_updater=True)
        assert_that(sub_entry.seat_limit.max_seats, is_(10))
        assert_that(cce.seat_limit.max_seats, none())

        # Remove seat limit obj
        ext_obj = dict(source_ext_obj)
        ext_obj['seat_limit'] = None
        update_from_external_object(cce, ext_obj, require_updater=True)
        
        cce_ext = to_external_object(cce)
        seat_limit_ext = cce_ext.get('seat_limit')
        assert_that(seat_limit_ext, none())
        
        assert_that(sub_entry.seat_limit, not_none())
        cce_ext = to_external_object(sub_entry)
        seat_limit_ext = cce_ext.get('seat_limit')
        assert_that(seat_limit_ext, has_entries('hard_limit', True,
                                                'max_seats', 10,
                                                'used_seats', 0))
        

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

from zope import component
from zope import interface

import unittest
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import contains
from hamcrest import has_item
from hamcrest import has_property
from hamcrest import calling
from hamcrest import raises
from hamcrest import not_none
from hamcrest import none
from hamcrest import same_instance

from zope.schema.interfaces import ConstraintNotSatisfied

from nti.testing import base
from nti.testing.matchers import is_empty
from nti.testing.matchers import validly_provides
from nti.testing.matchers import is_false

from .. import enrollment
from .. import interfaces
from .. import courses
from .. import catalog

from zope import lifecycleevent

from . import CourseLayerTest
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

class TestEnrollment(unittest.TestCase):

	def test_provides(self):
		assert_that( enrollment.DefaultCourseEnrollmentManager(None),
					 validly_provides(interfaces.ICourseEnrollmentManager))
		assert_that( enrollment.DefaultCourseInstanceEnrollmentRecord(),
					 validly_provides(interfaces.ICourseInstanceEnrollmentRecord))

		assert_that( enrollment.DefaultCourseEnrollments(None),
					 validly_provides(interfaces.ICourseEnrollments))

		assert_that( enrollment.DefaultPrincipalEnrollments(None),
					 validly_provides(interfaces.IPrincipalEnrollments))

		record = enrollment.DefaultCourseInstanceEnrollmentRecord()
		assert_that( record, has_property('Scope', 'Public'))

		assert_that( calling(setattr).with_args(record, 'Scope', 'not valid scope'),
					 raises(ConstraintNotSatisfied))


from zope.security.interfaces import IPrincipal
from zope.container.interfaces import IContained
from zope.location.interfaces import ISublocations
from ..interfaces import ICourseInstance
from ..interfaces import IEnrollmentMappedCourseInstance
from ..interfaces import ICourseInstanceVendorInfo
from zope.annotation.interfaces import IAttributeAnnotatable
from nti.wref.interfaces import IWeakRef
from nti.dataserver.interfaces import IUser
from zope.component import eventtesting
from zope.lifecycleevent import IObjectRemovedEvent

from nti.dataserver.sharing import SharingSourceMixin
from persistent import Persistent
import functools
from nti.dataserver.authentication import _dynamic_memberships_that_participate_in_security
from nti.dataserver.interfaces import ISharingTargetEntityIterable
from ..interfaces import ES_CREDIT
from ..interfaces import ES_CREDIT_NONDEGREE
from ..interfaces import ES_CREDIT_DEGREE
from ..interfaces import ES_PUBLIC
from ..interfaces import ICourseEnrollments

@functools.total_ordering
@interface.implementer(IPrincipal, IWeakRef, IContained, IAttributeAnnotatable)
class MockPrincipal(SharingSourceMixin, Persistent):
	username = id = 'MyPrincipal'
	__name__ = None
	__parent__ = None

	def __call__(self):
		return self

	def __eq__(self, other):
		return self is other

	def __ne__(self, other):
		return self is not other

	def __lt__(self, other):
		if other is not self:
			return True
		return False

class MockContentPackage(object):
	ntiid = "tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california."

class MockContentPackageBundle(object):

	@property
	def ContentPackages(self):
		return (MockContentPackage(),)


class TestFunctionalEnrollment(CourseLayerTest):

	principal = None
	course = None
	section = None
	course2 = None

	def _shared_setup(self):
		principal = MockPrincipal()
		self.ds.root[principal.id] = principal

		# we have to be IUser for the right Community event listeners
		# to fire.
		# Do this after adding to avoid setting up profile indexes, etc
		interface.alsoProvides(principal, IUser)

		admin = courses.CourseAdministrativeLevel()
		self.ds.root['admin'] = admin
		for name in 'course', 'course2':

			course = courses.ContentCourseInstance()
			admin[name] = course
			course.SharingScopes.initScopes()

			bundle = MockContentPackageBundle()
			# bypass field validation
			course.__dict__[str('ContentPackageBundle')] = bundle
			assert_that( course.ContentPackageBundle, is_( same_instance(bundle)))

		self.principal  = principal
		self.course = admin['course']
		self.course2 = admin['course2']

		course = self.course
		self.section = course.SubInstances['section1'] = courses.ContentCourseSubInstance()


	def _do_test_add_drop(self, principal, course,
						  enroll_scope='Public',
						  actually_enrolled_in_course=None,
						  extra_enroll_test=lambda: None):
		if actually_enrolled_in_course is None:
			actually_enrolled_in_course = course

		manager = interfaces.ICourseEnrollmentManager(course)
		assert_that( manager, is_(enrollment.DefaultCourseEnrollmentManager) )

		result = record = manager.enroll(principal, scope=enroll_scope)
		assert_that( result, is_(enrollment.DefaultCourseInstanceEnrollmentRecord ))

		# again does nothing
		assert_that( manager.enroll(principal, scope=enroll_scope), is_false() )
		self._check_enrolled(record, principal, actually_enrolled_in_course)

		# The record can be adapted to the course and the principal
		assert_that( record.Scope, is_(enroll_scope))
		assert_that( ICourseInstance(record), is_(actually_enrolled_in_course) )
		assert_that( IPrincipal(record), is_(principal))
		# (but not sublocations...earlier there was a bug that adapted
		# it to the course instance when asked for sublocations)
		assert_that( ISublocations(record, None), is_(none()) )

		extra_enroll_test()

		# now, we can drop, using the manager for the course we really
		# enrolled in
		manager = interfaces.ICourseEnrollmentManager(record.CourseInstance)
		eventtesting.clearEvents()
		result = record = manager.drop(principal)
		assert_that( result, is_(enrollment.DefaultCourseInstanceEnrollmentRecord ))

		evts = eventtesting.getEvents()
		# It all starts with the object-removed event:
		# [<zope.lifecycleevent.ObjectRemovedEvent object at 0x105f62f10>,
		#    <nti.intid.interfaces.IntIdRemovedEvent object at 0x105fa8610>,
		#    <zope.intid.interfaces.IntIdRemovedEvent object at 0x1058dbf50>,
		#    <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x1055ca390>,
		#    <nti.dataserver.interfaces.StopFollowingEvent object at 0x105483590>,
		#    <zc.intid.utility.RemovedEvent object at 0x105813cd0>,
		#   <zope.container.contained.ContainerModifiedEvent object at 0x1052244d0>]
		assert_that( evts[0], validly_provides(IObjectRemovedEvent) )
		assert_that( evts[0], has_property('object', is_(enrollment.DefaultCourseInstanceEnrollmentRecord)))


		# again does nothing
		eventtesting.clearEvents()
		assert_that( manager.drop(principal), is_false() )
		evts = eventtesting.getEvents()
		assert_that( evts, is_empty() )
		self._check_not_enrolled(principal, course)

	@WithMockDSTrans
	def test_enrollment_map_initial_enrollment(self):
		# When you try to for-credit-non-degree enroll in course, you
		# get thrown into section
		self._shared_setup()
		vendor_info = ICourseInstanceVendorInfo(self.course)
		vendor_info.setdefault('NTI', dict()).setdefault('EnrollmentMap',{})
		vendor_info['NTI']['EnrollmentMap']['ForCreditNonDegree'] = 'section1'
		interface.alsoProvides(self.course, IEnrollmentMappedCourseInstance)

		def extra_enroll_test():
			credit_scope = self.section.SharingScopes[ES_CREDIT]
			assert_that( list(credit_scope),
						 is_([self.principal]))

		self._do_test_add_drop(self.principal, self.course,
							   enroll_scope='ForCreditNonDegree',
							   actually_enrolled_in_course=self.section,
							   extra_enroll_test=extra_enroll_test
							   )

	@WithMockDSTrans
	def test_enrollment_map_change_scope(self):
		# If you initially enroll openly, you can get moved
		# into a new section by changing your scope
		self._shared_setup()
		vendor_info = ICourseInstanceVendorInfo(self.course)
		vendor_info.setdefault('NTI', dict()).setdefault('EnrollmentMap',{})
		vendor_info['NTI']['EnrollmentMap']['ForCreditNonDegree'] = 'section1'
		interface.alsoProvides(self.course, IEnrollmentMappedCourseInstance)

		# First, enroll openly
		open_manager = interfaces.ICourseEnrollmentManager(self.course)
		record = open_manager.enroll(self.principal)
		self._check_enrolled(record, self.principal, self.course)

		# Now modify the scope
		record.Scope = ES_CREDIT_NONDEGREE
		lifecycleevent.modified(record)

		# and things have moved
		assert_that( record.CourseInstance, is_(self.section))
		credit_scope = self.section.SharingScopes[ES_CREDIT]


		assert_that( list(credit_scope),
					 is_([self.principal]))

		self._check_enrolled(record, self.principal, self.section)
		self._check_not_enrolled(self.principal, self.course,
								 # we do have one enrollment still
								 expect_no_enrollments_for_principal=False,
								 # and we are actually in this public scope because we're
								 # in a sub-section
								 expect_not_in_public_scope=False)

	@WithMockDSTrans
	def test_add_drop(self):
		self._shared_setup()
		self._do_test_add_drop(self.principal, self.course)

	@WithMockDSTrans
	def test_add_drop_section(self):
		self._shared_setup()
		def extra_enroll_test():
			# When we are enrolled, we are also a member of the parent's
			# sharing scopes
			principal = self.principal
			public_scope = self.course.SharingScopes['Public']
			assert_that( public_scope,
						 is_not( same_instance(self.course.SubInstances['section1'].SharingScopes['Public'])))
			assert_that( principal, is_in(public_scope) )
			assert_that( public_scope, is_in(principal.dynamic_memberships))

			assert_that( _dynamic_memberships_that_participate_in_security(principal, as_principals=False),
						 has_item(public_scope))
			assert_that( _dynamic_memberships_that_participate_in_security(principal),
						 has_item(has_property('id', public_scope.NTIID)) )

		self._do_test_add_drop(self.principal, self.course.SubInstances['section1'],
							   extra_enroll_test=extra_enroll_test)

	@classmethod
	def _check_enrolled(cls, record, principal, course):
		# This is backed up by the two query utilities...

		assert_that( record.Principal, is_(principal))

		cin = interfaces.ICourseEnrollments(course)
		assert_that( cin.count_enrollments(), is_(1) )
		assert_that( list(cin.iter_enrollments()), contains( record ) )

		pins = component.subscribers( (principal,), interfaces.IPrincipalEnrollments )
		assert_that( pins, has_length(1) )
		pin = pins[0]
		assert_that(pin, is_(enrollment.DefaultPrincipalEnrollments))

		assert_that( list(pin.iter_enrollments()), contains(record) )

		# ... plus the scope memberships
		public_scope = course.SharingScopes['Public']

		assert_that( principal, is_in(public_scope) )
		assert_that( public_scope, is_in(list(principal.dynamic_memberships)))
		assert_that( list(_dynamic_memberships_that_participate_in_security(principal, as_principals=False)),
					 has_item(public_scope))
		assert_that( list(_dynamic_memberships_that_participate_in_security(principal)),
					 has_item(has_property('id', public_scope.NTIID)) )

	def _check_not_enrolled(self, principal, course,
							expect_no_enrollments_for_principal=True,
							expect_not_in_public_scope=True):
		cin = interfaces.ICourseEnrollments(course)
		assert_that( cin.count_enrollments(), is_(0) )
		assert_that( list(cin.iter_enrollments()), is_empty() )

		pins = component.subscribers( (principal,), interfaces.IPrincipalEnrollments )
		assert_that( pins, has_length(1) )
		pin = pins[0]
		assert_that(pin, is_(enrollment.DefaultPrincipalEnrollments))

		if expect_no_enrollments_for_principal:
			assert_that( list(pin.iter_enrollments()), is_empty() )

		# ...dropped from scope memberships
		public_scope = course.SharingScopes['Public']
		if expect_not_in_public_scope:
			assert_that( public_scope, is_not( is_in(list(principal.dynamic_memberships))))
			assert_that( principal, is_not(is_in(public_scope) ))
		else:
			assert_that( public_scope, is_in(list(principal.dynamic_memberships)))
			assert_that( principal, is_in(public_scope) )


	@WithMockDSTrans
	def test_delete_course_removes_enrollment_records(self):
		self._shared_setup()

		principal = self.principal
		course = self.course
		course_parent = self.course.__parent__

		manager = interfaces.ICourseEnrollmentManager(course)
		assert_that( manager, is_(enrollment.DefaultCourseEnrollmentManager) )

		record = manager.enroll(principal)
		self._check_enrolled(record, principal, course)

		assert_that( record, has_property('__parent__', not_none() ))

		eventtesting.clearEvents()
		del course_parent[course.__name__]

		# all the enrollment stuff was cleaned up
		self._check_not_enrolled(principal, course)

		# including un-parenting the record
		assert_that( record, has_property('__parent__', none() ))

	@WithMockDSTrans
	def test_delete_principal_removes_enrollment_records(self):
		self._shared_setup()

		principal = self.principal
		course = self.course
		course_parent = self.course.__parent__

		manager = interfaces.ICourseEnrollmentManager(course)
		assert_that( manager, is_(enrollment.DefaultCourseEnrollmentManager) )

		record = manager.enroll(principal)
		self._check_enrolled(record, principal, course)

		assert_that( record, has_property('__parent__', not_none() ))
		assert_that( record, has_property('_ds_intid', not_none() ))

		lifecycleevent.removed(principal)

		# all the enrollment stuff was cleaned up
		self._check_not_enrolled(principal, course)

		# including un-parenting the record
		assert_that( record, has_property('__parent__', none() ))
		assert_that( record, has_property('_ds_intid', none() ))


	@WithMockDSTrans
	def test_migrate_enrolments(self):
		self._shared_setup()

		principal = self.principal
		orig_course = self.course

		manager = interfaces.ICourseEnrollmentManager(orig_course)
		record = manager.enroll(principal, scope=ES_CREDIT_DEGREE)

		public = orig_course.SharingScopes[ES_PUBLIC]
		credit = orig_course.SharingScopes[ES_CREDIT]
		degree = orig_course.SharingScopes[ES_CREDIT_DEGREE]
		ndgree = orig_course.SharingScopes[ES_CREDIT_NONDEGREE]

		assert_that( principal, is_in(public) )
		assert_that( principal, is_in(credit) )
		assert_that( principal, is_in(degree) )
		assert_that( principal, is_not(is_in(ndgree)) )

		new_course = self.course2
		from ..enrollment import migrate_enrollments_from_course_to_course
		eventtesting.clearEvents()

		migrate_enrollments_from_course_to_course(orig_course, new_course)

		# So he left everything from the old course:

		assert_that( principal, is_not(is_in(public) ))
		assert_that( principal, is_not(is_in(credit) ))
		assert_that( principal, is_not(is_in(degree) ))
		assert_that( principal, is_not(is_in(ndgree)))

		# ...and is in the things from the new course

		public = new_course.SharingScopes[ES_PUBLIC]
		credit = new_course.SharingScopes[ES_CREDIT]
		degree = new_course.SharingScopes[ES_CREDIT_DEGREE]
		ndgree = new_course.SharingScopes[ES_CREDIT_NONDEGREE]

		assert_that( principal, is_in(public) )
		assert_that( principal, is_in(credit) )
		assert_that( principal, is_in(degree) )
		assert_that( principal, is_not(is_in(ndgree)) )

		# Only the desired events fired

		# [<zope.lifecycleevent.ObjectMovedEvent object at 0x1039fbc50>,
		#  <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x1039fb8d0>,
		#   <nti.dataserver.interfaces.StopFollowingEvent object at 0x103a1b690>,
		#  <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x103a1bd10>,
		#  <nti.dataserver.interfaces.StopFollowingEvent object at 0x103a1b590>,
		#  <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x103a1bb90>,
		#  <nti.dataserver.interfaces.StopFollowingEvent object at 0x1049c69d0>,
		#  <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1044d1050>,
		# <nti.dataserver.interfaces.EntityFollowingEvent object at 0x1039fb950>,
		# <nti.dataserver.interfaces.FollowerAddedEvent object at 0x1049d2990>,
		# <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1021df710>,
		# <nti.dataserver.interfaces.EntityFollowingEvent object at 0x103673990>,
		# <nti.dataserver.interfaces.FollowerAddedEvent object at 0x103673950>,
		# <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x103673910>,
		# <nti.dataserver.interfaces.EntityFollowingEvent object at 0x103673b90>,
		# <nti.dataserver.interfaces.FollowerAddedEvent object at 0x103673c10>,
		# <zope.container.contained.ContainerModifiedEvent object at 0x1039fb9d0>,
		# <zope.container.contained.ContainerModifiedEvent object at 0x1039fba50>]
		evts = eventtesting.getEvents()
		# XXX Not a good test
		assert_that( evts, has_length(18))

		assert_that(ICourseEnrollments(orig_course).count_enrollments(),
					is_(0))
		assert_that(ICourseEnrollments(new_course).count_enrollments(),
					is_(1))

		# If we enroll in the original course again:
		record2 = manager.enroll(principal, scope=ES_CREDIT_DEGREE)
		assert_that( record2, is_not(same_instance(record)))
		eventtesting.clearEvents()

		# trying to migrate does nothing
		migrate_enrollments_from_course_to_course(orig_course, new_course)

		evts = eventtesting.getEvents()
		assert_that( evts, has_length(0))

		assert_that(ICourseEnrollments(orig_course).count_enrollments(),
					is_(1))
		assert_that(ICourseEnrollments(new_course).count_enrollments(),
					is_(1))

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge

from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import contains
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import same_instance
from hamcrest import contains_inanyorder

from nti.testing.matchers import is_empty
from nti.testing.matchers import validly_provides

import unittest

from nti.contenttypes.courses import sharing
from nti.contenttypes.courses import interfaces

class TestSharing(unittest.TestCase):

	def test_provides(self):
		assert_that( sharing.CourseInstanceSharingScope('foo'),
					 validly_provides(interfaces.ICourseInstanceSharingScope))
		assert_that( sharing.CourseInstanceSharingScopes(),
					 validly_provides(interfaces.ICourseInstanceSharingScopes))

	def test_get_scopes(self):
		scopes = sharing.CourseInstanceSharingScopes()

		all_scopes = scopes.getAllScopesImpliedbyScope('ForCreditNonDegree')
		all_scopes = list(all_scopes)

		assert_that( all_scopes,
					 contains_inanyorder(
						 has_property('__name__', interfaces.ES_PUBLIC ),
						 has_property('__name__', interfaces.ES_CREDIT ),
						 has_property('__name__', interfaces.ES_PURCHASED ),
						 has_property('__name__', interfaces.ES_CREDIT_NONDEGREE )
					 ))

import functools

from zope import interface
from zope import component
from zope import lifecycleevent

from zope.annotation.interfaces import IAttributeAnnotatable

from zope.component import eventtesting

from zope.container.interfaces import IContained

from zope.copypastemove import IObjectMover

from zope.security.interfaces import IPrincipal

from nti.contenttypes.courses import courses
from nti.contenttypes.courses.interfaces import ES_PUBLIC, ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT, ES_CREDIT_NONDEGREE, ES_CREDIT_DEGREE

from nti.dataserver.users import User
from nti.dataserver.interfaces import IUser
from nti.dataserver.sharing import SharingSourceMixin
from nti.dataserver import interfaces as nti_interfaces
from nti.dataserver.authorization import CONTENT_ROLE_PREFIX
from nti.dataserver.authorization import role_for_providers_content

from nti.ntiids import ntiids

from nti.schema.schema import EqHash

from nti.wref.interfaces import IWeakRef

from persistent import Persistent

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

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

@EqHash( 'ntiid' )
class MockContentPackage(object):
	ntiid = "tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california."

class MockContentPackageBundle(object):

	@property
	def ContentPackages(self):
		return (MockContentPackage(),)

class TestFunctionalSharing(CourseLayerTest):

	principal = None
	course = None
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

			sub = course.SubInstances['child'] = courses.ContentCourseSubInstance()
			sub.__dict__[str('ContentPackageBundle')] = bundle
			sub.SharingScopes.initScopes()

		self.principal  = principal
		self.course = admin['course']
		self.course2 = admin['course2']

	@WithMockDSTrans
	def test_content_roles(self):
		self._shared_setup()

		provider = ntiids.get_provider(MockContentPackage.ntiid)
		specific = ntiids.get_specific(MockContentPackage.ntiid)
		role = role_for_providers_content(provider, specific)

		principal = self.principal
		member = component.getAdapter( principal, nti_interfaces.IMutableGroupMember, CONTENT_ROLE_PREFIX )
		assert_that( list(member.groups), is_empty() )

		course = self.course

		manager = interfaces.ICourseEnrollmentManager(course)
		manager.enroll(principal, scope=ES_CREDIT_DEGREE)

		assert_that( list(member.groups), contains(role))

		manager.drop(principal)

		assert_that( list(member.groups), is_empty() )

	@WithMockDSTrans
	def test_usernames_of_dynamic_memberships(self):
		self._shared_setup()
		user = User.create_user(username="nti@nti.com")

		course = self.course
		manager = interfaces.ICourseEnrollmentManager(course)
		manager.enroll(user, scope=ES_CREDIT_DEGREE)
		degree = course.SharingScopes[ES_CREDIT_DEGREE]
		ntiid = degree.NTIID

		names = list(user.usernames_of_dynamic_memberships)
		assert_that(ntiid, is_in(names))

	@WithMockDSTrans
	def test_purchased(self):
		self._shared_setup()
		principal = self.principal

		course = self.course
		manager = interfaces.ICourseEnrollmentManager(course)
		manager.enroll(principal, scope=ES_PURCHASED)

		public = course.SharingScopes[ES_PUBLIC]
		purchased = course.SharingScopes[ES_PURCHASED]

		assert_that( principal, is_in(public) )
		assert_that( principal, is_in(purchased) )

	@WithMockDSTrans
	@fudge.patch( 'nti.contenttypes.courses.sharing.get_enrollments' )
	def test_sub_and_parent_drop_parent(self, mock_get_enroll):
		self._shared_setup()
		# Need to mock out enrollments since these are mock courses.
		mock_get_enroll.is_callable().returns(())

		provider = ntiids.get_provider(MockContentPackage.ntiid)
		specific = ntiids.get_specific(MockContentPackage.ntiid)
		role = role_for_providers_content(provider, specific)

		principal = self.principal
		member = component.getAdapter( principal, nti_interfaces.IMutableGroupMember, CONTENT_ROLE_PREFIX )
		assert_that( list(member.groups), is_empty() )

		course = self.course
		sub_course = self.course.SubInstances['child']

		manager = interfaces.ICourseEnrollmentManager(course)
		manager.enroll(principal, scope=ES_CREDIT_DEGREE)

		public = course.SharingScopes[ES_PUBLIC]
		credit = course.SharingScopes[ES_CREDIT]
		degree = course.SharingScopes[ES_CREDIT_DEGREE]
		ndgree = course.SharingScopes[ES_CREDIT_NONDEGREE]

		assert_that( principal, is_in(public) )
		assert_that( principal, is_in(credit) )
		assert_that( principal, is_in(degree) )
		assert_that( principal, is_not(is_in(ndgree)) )

		submanager = interfaces.ICourseEnrollmentManager(sub_course)
		record2 = submanager.enroll(principal, scope=ES_CREDIT_DEGREE)
		assert_that( list(member.groups), contains(role))
		# Drop the parent first; this is mocked for the underlying subscribers
		# of drop.
		mock_get_enroll.is_callable().returns( (record2,) )
		manager.drop(principal)

		# Unenrolling does not lose our role
		assert_that( list(member.groups), contains(role))

		# and still in the correct scopes
		public = course.SharingScopes[ES_PUBLIC]
		credit = course.SharingScopes[ES_CREDIT]
		degree = course.SharingScopes[ES_CREDIT_DEGREE]
		ndgree = course.SharingScopes[ES_CREDIT_NONDEGREE]

		assert_that( principal, is_in(public) )
		assert_that( principal, is_in(credit) )
		assert_that( principal, is_in(degree) )
		assert_that( principal, is_not(is_in(ndgree)) )

		sub_public = sub_course.SharingScopes[ES_PUBLIC]
		sub_credit = sub_course.SharingScopes[ES_CREDIT]
		sub_degree = sub_course.SharingScopes[ES_CREDIT_DEGREE]
		sub_ndgree = sub_course.SharingScopes[ES_CREDIT_NONDEGREE]

		assert_that( principal, is_in(sub_public) )
		assert_that( principal, is_in(sub_credit) )
		assert_that( principal, is_in(sub_degree) )
		assert_that( principal, is_not(is_in(sub_ndgree)) )

		mock_get_enroll.is_callable().returns( () )
		submanager.drop(principal)
		# Now gone from the roles
		assert_that( list(member.groups), is_empty() )

		# and all the scopes
		assert_that( principal, is_not(is_in(public) ))
		assert_that( principal, is_not(is_in(credit) ))
		assert_that( principal, is_not(is_in(degree) ))
		assert_that( principal, is_not(is_in(ndgree)))

		assert_that( principal, is_not(is_in(sub_public) ))
		assert_that( principal, is_not(is_in(sub_credit) ))
		assert_that( principal, is_not(is_in(sub_degree) ))
		assert_that( principal, is_not(is_in(sub_ndgree)))

	@WithMockDSTrans
	def test_change_scope(self):
		self._shared_setup()

		principal = self.principal
		course = self.course

		manager = interfaces.ICourseEnrollmentManager(course)
		record = manager.enroll(principal, scope=ES_CREDIT_DEGREE)

		public = course.SharingScopes[ES_PUBLIC]
		credit = course.SharingScopes[ES_CREDIT]
		purchased = course.SharingScopes[ES_PURCHASED]
		degree = course.SharingScopes[ES_CREDIT_DEGREE]
		ndgree = course.SharingScopes[ES_CREDIT_NONDEGREE]

		assert_that( principal, is_in(public) )
		assert_that( principal, is_in(credit) )
		assert_that( principal, is_in(degree) )
		assert_that( principal, is_in(purchased) )
		assert_that( principal, is_not(is_in(ndgree)) )

		record.Scope = ES_CREDIT_NONDEGREE
		lifecycleevent.modified(record)

		assert_that( principal, is_in(public) )
		assert_that( principal, is_in(credit) )
		assert_that( principal, is_in(purchased) )
		assert_that( principal, is_not(is_in(degree) ))
		assert_that( principal, is_in(ndgree))

		record.Scope = ES_PUBLIC
		lifecycleevent.modified(record)

		assert_that( principal, is_in(public) )
		assert_that( principal, is_not(purchased) )
		assert_that( principal, is_not(is_in(credit) ))
		assert_that( principal, is_not(is_in(degree) ))
		assert_that( principal, is_not(is_in(ndgree)))

	@WithMockDSTrans
	def test_change_scope_through_move(self):
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
		from nti.contenttypes.courses.enrollment import IDefaultCourseInstanceEnrollmentStorage

		mover = IObjectMover(record)

		eventtesting.clearEvents()

		mover.moveTo(IDefaultCourseInstanceEnrollmentStorage(new_course))

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
# 		[<zope.lifecycleevent.ObjectMovedEvent object at 0x1066d3e10>,
# 		 <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x1066d3d10>,
# 		 <nti.dataserver.interfaces.StopFollowingEvent object at 0x1066d3fd0>,
# 		 <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x1066d3090>,
# 		 <nti.dataserver.interfaces.StopFollowingEvent object at 0x1066d3110>,
# 		 <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x1066d31d0>,
# 		 <nti.dataserver.interfaces.StopFollowingEvent object at 0x103be2250>,
# 		 <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x103be2410>,
# 		 <nti.dataserver.interfaces.StopFollowingEvent object at 0x1066cc810>,
# 		 <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1066cc210>,
# 		 <nti.dataserver.interfaces.EntityFollowingEvent object at 0x1066cc310>,
# 		 <nti.dataserver.interfaces.FollowerAddedEvent object at 0x1066cc150>,
# 		 <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1066cc510>,
# 		 <nti.dataserver.interfaces.EntityFollowingEvent object at 0x1066cc250>,
# 		 <nti.dataserver.interfaces.FollowerAddedEvent object at 0x1066cc410>,
# 		 <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1066cc0d0>,
# 		 <nti.dataserver.interfaces.EntityFollowingEvent object at 0x1066cc4d0>,
# 		 <nti.dataserver.interfaces.FollowerAddedEvent object at 0x1066cc1d0>,
# 		 <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1066cc050>,
# 		 <nti.dataserver.interfaces.EntityFollowingEvent object at 0x1066cc390>,
# 		 <nti.dataserver.interfaces.FollowerAddedEvent object at 0x1066cc3d0>,
# 		 <zope.container.contained.ContainerModifiedEvent object at 0x1066d3f10>,
# 		 <zope.container.contained.ContainerModifiedEvent object at 0x1066d3250>]
		evts = eventtesting.getEvents()
		# XXX Not a good test
		assert_that( evts, has_length(23))

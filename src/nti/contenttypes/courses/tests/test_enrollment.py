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
from hamcrest import has_property
from hamcrest import calling
from hamcrest import raises
from hamcrest import not_none
from hamcrest import none

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
from zope.annotation.interfaces import IAttributeAnnotatable
from nti.wref.interfaces import IWeakRef
from nti.dataserver.interfaces import IUser

from nti.dataserver.sharing import SharingSourceMixin
from persistent import Persistent
import functools
from nti.dataserver.authentication import _dynamic_memberships_that_participate_in_security

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


class TestFunctionalEnrollment(CourseLayerTest):

	old_gcc = None

	def setUp(self):
		CourseLayerTest.setUp(self)
		# If we are using the global course catalog, we wind up
		# storing persistent annotations in it across transactions,
		# and in fact associating it with a connection (because it is persistent)
		# which doesn't work. So we swap in a new one each time
		self.old_gcc = component.getUtility(interfaces.ICourseCatalog)
		component.getGlobalSiteManager().registerUtility(catalog.GlobalCourseCatalog(),
														 interfaces.ICourseCatalog)
	def tearDown(self):
		component.getGlobalSiteManager().registerUtility(self.old_gcc,
														 interfaces.ICourseCatalog)


	principal = None
	course = None
	def _shared_setup(self):
		principal = MockPrincipal()
		self.ds.root[principal.id] = principal

		# we have to be IUser for the right Community event listeners
		# to fire.
		# Do this after adding to avoid setting up profile indexes, etc
		interface.alsoProvides(principal, IUser)

		admin = courses.CourseAdministrativeLevel()
		self.ds.root['admin'] = admin
		course = courses.CourseInstance()
		admin['course'] = course

		self.principal  = principal
		self.course = course

	@WithMockDSTrans
	def test_add_drop(self):
		self._shared_setup()

		principal = self.principal
		course = self.course

		manager = interfaces.ICourseEnrollmentManager(course)
		assert_that( manager, is_(enrollment.DefaultCourseEnrollmentManager) )

		result = record = manager.enroll(principal)
		assert_that( result, is_(enrollment.DefaultCourseInstanceEnrollmentRecord ))

		# again does nothing
		assert_that( manager.enroll(principal), is_false() )
		self._check_enrolled(record, principal, course)

		# now, we can drop
		result = record = manager.drop(principal)
		assert_that( result, is_(enrollment.DefaultCourseInstanceEnrollmentRecord ))
		# again does nothing
		assert_that( manager.drop(principal), is_false() )
		self._check_not_enrolled(principal, course)

	def _check_enrolled(self, record, principal, course):
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
		assert_that( public_scope, is_in(principal.dynamic_memberships))

		assert_that( _dynamic_memberships_that_participate_in_security(principal, as_principals=False),
					 contains(public_scope))
		assert_that( _dynamic_memberships_that_participate_in_security(principal),
					 contains(has_property('id', public_scope.NTIID)) )

	def _check_not_enrolled(self, principal, course):
		cin = interfaces.ICourseEnrollments(course)
		assert_that( cin.count_enrollments(), is_(0) )
		assert_that( list(cin.iter_enrollments()), is_empty() )

		pins = component.subscribers( (principal,), interfaces.IPrincipalEnrollments )
		assert_that( pins, has_length(1) )
		pin = pins[0]
		assert_that(pin, is_(enrollment.DefaultPrincipalEnrollments))

		assert_that( list(pin.iter_enrollments()), is_empty() )

		# ...dropped from scope memberships
		public_scope = course.SharingScopes['Public']
		assert_that( public_scope, is_not( is_in(principal.dynamic_memberships)))
		assert_that( principal, is_not(is_in(public_scope) ))


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

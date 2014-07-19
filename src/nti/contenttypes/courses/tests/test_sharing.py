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

import unittest
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import contains_inanyorder
from hamcrest import has_property
from hamcrest import is_in
from hamcrest import is_not

from nti.testing.matchers import validly_provides

from .. import sharing
from .. import interfaces


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
						 has_property('__name__', interfaces.ES_CREDIT_NONDEGREE )
					 ))


from zope import interface
from zope.security.interfaces import IPrincipal
from zope.container.interfaces import IContained
from zope.annotation.interfaces import IAttributeAnnotatable
from nti.wref.interfaces import IWeakRef
from nti.dataserver.interfaces import IUser

from nti.dataserver.sharing import SharingSourceMixin
from persistent import Persistent
import functools

from .. import interfaces
from ..interfaces import ES_PUBLIC, ES_CREDIT, ES_CREDIT_NONDEGREE, ES_CREDIT_DEGREE
from .. import courses

from zope import lifecycleevent

from . import CourseLayerTest
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


class TestFunctionalSharing(CourseLayerTest):

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
		course.SharingScopes.initScopes()

		self.principal  = principal
		self.course = course

	@WithMockDSTrans
	def test_change_scope(self):
		self._shared_setup()

		principal = self.principal
		course = self.course

		manager = interfaces.ICourseEnrollmentManager(course)
		record = manager.enroll(principal, scope=ES_CREDIT_DEGREE)

		public = course.SharingScopes[ES_PUBLIC]
		credit = course.SharingScopes[ES_CREDIT]
		degree = course.SharingScopes[ES_CREDIT_DEGREE]
		ndgree = course.SharingScopes[ES_CREDIT_NONDEGREE]

		assert_that( principal, is_in(public) )
		assert_that( principal, is_in(credit) )
		assert_that( principal, is_in(degree) )
		assert_that( principal, is_not(is_in(ndgree)) )

		record.Scope = ES_CREDIT_NONDEGREE
		lifecycleevent.modified(record)

		assert_that( principal, is_in(public) )
		assert_that( principal, is_in(credit) )
		assert_that( principal, is_not(is_in(degree) ))
		assert_that( principal, is_in(ndgree))

		record.Scope = ES_PUBLIC
		lifecycleevent.modified(record)

		assert_that( principal, is_in(public) )
		assert_that( principal, is_not(is_in(credit) ))
		assert_that( principal, is_not(is_in(degree) ))
		assert_that( principal, is_not(is_in(ndgree)))

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
from hamcrest import empty
from hamcrest import contains

from nti.testing import base
from nti.testing.matchers import validly_provides

from ..principalrole import CourseInstancePrincipalRoleMap
from ..interfaces import RID_TA
from ..interfaces import RID_INSTRUCTOR
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import Unset

class _PhonyPrincipal(object):
	id = None

	def __init__(self, id):
		self.id = id

class _PhonyCourse(object):

	instructors = []

	def __init__(self):
		self.instructors = []

	def _add_instructor(self, id):
		self.instructors.append(_PhonyPrincipal(id))

class TestCourseInstancePrincipalRoleMap(unittest.TestCase):

	course = None
	rolemap = None

	def setUp(self):
		super(TestCourseInstancePrincipalRoleMap,self).setUp()
		self.course = _PhonyCourse()
		self.rolemap = CourseInstancePrincipalRoleMap(self.course)

	def test_provides(self):
		assert_that( self.rolemap, validly_provides(IPrincipalRoleMap) )

	def test_principals_for_role(self):
		# initially empty, no instructors
		assert_that( self.rolemap.getPrincipalsForRole('foo'), is_(empty()))
		assert_that( self.rolemap.getPrincipalsForRole(RID_TA), is_(empty()))
		assert_that( self.rolemap.getPrincipalsForRole(RID_INSTRUCTOR), is_(empty()))

		self.course._add_instructor('foo')

		assert_that( self.rolemap.getPrincipalsForRole(RID_TA), is_(empty()))
		assert_that( self.rolemap.getPrincipalsForRole(RID_INSTRUCTOR),
					 contains( ('foo', Allow) ) )

	def test_roles_for_principal(self):
		assert_that( self.rolemap.getRolesForPrincipal('foo'), is_(empty()))
		self.course._add_instructor('foo')

		assert_that( self.rolemap.getRolesForPrincipal('foo'),
					 contains( (RID_INSTRUCTOR, Allow) ))
		assert_that( self.rolemap.getRolesForPrincipal('foo2'), is_(empty()))

	def test_get_setting(self):
		assert_that( self.rolemap.getSetting('bad role', None),
					 is_(Unset) )
		assert_that( self.rolemap.getSetting(RID_TA, 'foo'),
					 is_(Unset))

		self.course._add_instructor('foo')

		assert_that( self.rolemap.getSetting(RID_INSTRUCTOR, 'foo'),
					 is_(Allow))
		assert_that( self.rolemap.getSetting(RID_TA, 'foo'),
					 is_(Unset))


	def test_get_all(self):
		assert_that( self.rolemap.getPrincipalsAndRoles(),
					 is_(empty()))

		self.course._add_instructor('foo')

		assert_that( self.rolemap.getPrincipalsAndRoles(),
					 contains( (RID_INSTRUCTOR, 'foo', Allow) ) )

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904


from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import contains_inanyorder


from .. import courses

from . import CourseLayerTest

import os.path
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
from nti.dataserver.users import User

from .._role_parser import fill_roles_from_key


from nti.contentlibrary.filesystem import FilesystemKey
from zope.securitypolicy.interfaces import Allow, Deny
from zope.security.interfaces import IPrincipal

class TestRoleParser(CourseLayerTest):


	@WithMockDSTrans
	def test_parse(self):
		unames = ('jmadden', 'steve.johnson@nextthought.com', 'harp4162', 'orig_instructor')
		users = {}
		for uname in unames:
			u = User.create_user(dataserver=self.ds, username=uname)
			users[uname] = u

		path = os.path.join( os.path.dirname(__file__),
							 'TestSynchronizeWithSubInstances',
							 'Spring2014',
							 'Gateway',
							 'role_info.json')
		key = FilesystemKey()
		key.absolute_path = path

		inst = courses.CourseInstance()
		self.ds.dataserver_folder._p_jar.add(inst)
		inst.SharingScopes.initScopes()

		for scope in inst.SharingScopes.values():
			users['orig_instructor'].record_dynamic_membership(scope)
		inst.instructors = (IPrincipal(users['orig_instructor']),)

		roles = fill_roles_from_key( inst, key )

		assert_that( roles.lastModified, is_(key.lastModified) )

		assert_that( roles.getSetting('nti.roles.course_ta', 'jmadden'),
					 is_(Allow))
		assert_that( roles.getSetting('nti.roles.course_instructor', 'steve.johnson@nextthought.com'),
					 is_(Deny))

		assert_that( roles.getSetting('nti.roles.course_instructor', 'harp4162'),
					 is_(Allow))

		assert_that( inst.instructors, contains_inanyorder(IPrincipal(users['jmadden']),
														   IPrincipal(users['harp4162']) ) )

		for scope in inst.SharingScopes.values():
			assert_that( users['harp4162'], is_in(scope) )
			assert_that( users['orig_instructor'], is_not(is_in(scope)))

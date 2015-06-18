#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import contains_inanyorder

import os.path

from zope.interface import directlyProvides

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow, Deny
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.contentlibrary.filesystem import FilesystemKey

from nti.contenttypes.courses.courses import CourseInstance
from nti.contenttypes.courses.courses import CourseSubInstances

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.courses._role_parser import fill_roles_from_key

from nti.dataserver.users import User

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

class TestRoleParser(CourseLayerTest):

	def setup_users(self):
		unames = ('jmadden', 'steve.johnson@nextthought.com', 'harp4162', 'orig_instructor')
		users = {}
		for uname in unames:
			u = User.create_user(dataserver=self.ds, username=uname)
			users[uname] = u
		return users

	@WithMockDSTrans
	def test_parse(self):
		users = self.setup_users()
		path = os.path.join(os.path.dirname(__file__),
							 'TestSynchronizeWithSubInstances',
							 'Spring2014',
							 'Gateway',
							 'role_info.json')
		key = FilesystemKey()
		key.absolute_path = path

		inst = CourseInstance()
		self.ds.dataserver_folder._p_jar.add(inst)
		inst.SharingScopes.initScopes()

		for scope in inst.SharingScopes.values():
			users['orig_instructor'].record_dynamic_membership(scope)
		inst.instructors = (IPrincipal(users['orig_instructor']),)

		fill_roles_from_key(inst, key)
		roles = IPrincipalRoleManager(inst)

		assert_that(roles.getSetting('nti.roles.course_ta', 'jmadden'),
					is_(Allow))
		assert_that(roles.getSetting('nti.roles.course_instructor', 'steve.johnson@nextthought.com'),
					is_(Deny))

		assert_that(roles.getSetting('nti.roles.course_instructor', 'harp4162'),
					is_(Allow))

		assert_that(inst.instructors, contains_inanyorder(IPrincipal(users['jmadden']),
														  IPrincipal(users['harp4162'])))

		for scope in inst.SharingScopes.values():
			assert_that(users['harp4162'], is_in(scope))
			assert_that(users['orig_instructor'], is_not(is_in(scope)))

	@WithMockDSTrans
	def test_section_parse(self):
		users = self.setup_users()
		path = os.path.join(os.path.dirname(__file__),
							 'TestSynchronizeWithSubInstances',
							 'Spring2014',
							 'Gateway',
							 'Sections',
							 '03',
							 'role_info.json')
		key = FilesystemKey()
		key.absolute_path = path

		# Setup our course structure
		parent_course = CourseInstance()
		section_course = CourseInstance()
		directlyProvides(section_course, ICourseSubInstance)
		section_course.__parent__ = CourseSubInstances()
		section_course.__parent__.__parent__ = parent_course

		self.ds.dataserver_folder._p_jar.add(parent_course)
		self.ds.dataserver_folder._p_jar.add(section_course)

		parent_course.SharingScopes.initScopes()
		section_course.SharingScopes.initScopes()

		# Section roles loaded
		fill_roles_from_key(section_course, key)

		section_instructor = 'steve.johnson@nextthought.com'

		assert_that(section_course.instructors,
					contains_inanyorder(IPrincipal(users[section_instructor])))

		for scope in section_course.SharingScopes.values():
			assert_that(users[ section_instructor ], is_in(scope))

		parent_scopes = parent_course.SharingScopes
		parent_public_scope = parent_scopes[ES_PUBLIC]
		for scope in parent_course.SharingScopes.values():
			# Section instructor is *only* in parent public scope.
			if scope == parent_public_scope:
				assert_that(users[ section_instructor ],
							is_in(parent_public_scope))
			else:
				assert_that(users[ section_instructor ],
							is_not(is_in(scope)))

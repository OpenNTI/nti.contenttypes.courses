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
from hamcrest import has_property
from hamcrest import has_entry
from hamcrest import has_entries
from hamcrest import not_none
from hamcrest import same_instance

from nti.testing import base
from nti.testing import matchers

from nti.testing.matchers import verifiably_provides
from nti.externalization.tests import externalizes


from .. import courses
from .. import interfaces

from . import CourseLayerTest

import os.path
from nti.testing.matchers import verifiably_provides

from .._role_parser import fill_roles_from_key
from ..legacy_catalog import PersistentCourseCatalogLegacyEntry as CourseCatalogLegacyEntry
from ..legacy_catalog import ICourseCatalogLegacyEntry

from nti.contentlibrary.filesystem import FilesystemKey
from zope.securitypolicy.interfaces import Allow, Deny
from zope.security.interfaces import IPrincipal

class TestRoleParser(CourseLayerTest):


	def test_parse(self):
		path = os.path.join( os.path.dirname(__file__),
							 'TestSynchronizeWithSubInstances',
							 'Spring2014',
							 'Gateway',
							 'role_info.json')
		key = FilesystemKey()
		key.absolute_path = path

		inst = courses.CourseInstance()

		roles = fill_roles_from_key( inst, key )

		assert_that( roles.lastModified, is_(key.lastModified) )

		assert_that( roles.getSetting('nti.roles.course_ta', 'jmadden'),
					 is_(Allow))
		assert_that( roles.getSetting('nti.roles.course_instructor', 'steve.johnson@nextthought.com'),
					 is_(Deny))

		assert_that( roles.getSetting('nti.roles.course_instructor', 'harp4162'),
					 is_(Allow))

		assert_that( inst.instructors, is_((IPrincipal('harp4162'),)))

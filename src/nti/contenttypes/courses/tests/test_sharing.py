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

from nti.testing import base
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

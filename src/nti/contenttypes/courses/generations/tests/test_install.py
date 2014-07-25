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
from hamcrest import has_key

from nti.dataserver.tests.mock_dataserver import DataserverLayerTest
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
from nti.dataserver.tests import mock_dataserver

class TestFunctionalInstall(DataserverLayerTest):

	@WithMockDSTrans
	def test_installed(self):
		conn = mock_dataserver.current_transaction
		root = conn.root()
		generations = root['zope.generations']

		assert_that( generations, has_key('nti.dataserver-AAA.contenttypes.courses'))

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# We can simply reuse the dataserver test layer and
# test case because its auto-include mechanism
# will pull us in too.
# But we define some values in case we need to change this later

from nti.dataserver.tests.mock_dataserver import DataserverTestLayer
from nti.dataserver.tests.mock_dataserver import DataserverLayerTest

class CourseTestLayer(DataserverTestLayer):

	@classmethod
	def setUp(cls):
		pass
	tearDown = setUp
	setUpTest= setUp
	tearDownTest = setUp

class CourseLayerTest(DataserverLayerTest):

	layer = CourseTestLayer

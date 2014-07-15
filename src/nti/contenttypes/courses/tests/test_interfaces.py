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
from hamcrest import has_key
from hamcrest import has_entry
import unittest

from zope.dottedname import resolve as dottedname

class TestImport(unittest.TestCase):

	def test_import_interfaces(self):
		dottedname.resolve('nti.contenttypes.courses.interfaces')

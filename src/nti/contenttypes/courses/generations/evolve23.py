#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 23

from nti.contenttypes.courses.generations import evolve21

def evolve(context):
	"""
	Evolve to generation 23 by reindexing the courses
	"""
	evolve21.do_evolve(context, generation)

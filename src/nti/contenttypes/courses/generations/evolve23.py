#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

generation = 23

from nti.contenttypes.courses.generations import evolve21

def evolve(context):
	"""
	Evolve to generation 23 by reindexing the courses
	"""
	evolve21.do_evolve(context, generation)

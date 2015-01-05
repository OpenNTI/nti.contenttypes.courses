#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 3.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 3

from .evolve2 import do_evolve
			
def evolve(context):
	"""
	Evolve to generation 3 by putting all enrollment records in the metadata queue
	"""
	do_evolve(context, generation)

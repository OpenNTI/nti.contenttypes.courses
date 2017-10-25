#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.contenttypes.courses.generations import evolve21

generation = 23


def evolve(context):
    """
    Evolve to generation 23 by reindexing the courses
    """
    evolve21.do_evolve(context, generation)

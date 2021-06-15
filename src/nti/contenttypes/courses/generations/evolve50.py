#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.contenttypes.courses.generations.evolve47 import do_evolve

generation = 50

logger = __import__('logging').getLogger(__name__)


def evolve(context):
    """
    Evolve to generation 50 by reindexing courses in the deleted
    and non-public topic indexes.
    """
    do_evolve(context, generation)

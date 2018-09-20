#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Traversal related objects.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.traversing.interfaces import IPathAdapter

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPathAdapter)
def CourseCatalogEntryTraverser(instance, unused_obj=None):
    """
    Courses can be traversed to their catalog entry.
    """
    return ICourseCatalogEntry(instance)

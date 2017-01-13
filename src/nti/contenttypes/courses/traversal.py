#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Traversal related objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope.traversing.interfaces import IPathAdapter

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry


@interface.implementer(IPathAdapter)
def CourseCatalogEntryTraverser(instance, request):
    """
    Courses can be traversed to their catalog entry.
    """
    return ICourseCatalogEntry(instance)

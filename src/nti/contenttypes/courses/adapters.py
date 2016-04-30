#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseKeywords

from nti.contenttypes.courses.utils import get_course_vendor_info

class _Keywords(object):
    
    __slots__ = b'keywords'
    
    def __init__(self, keywords=()):
        self.keywords = keywords

@component.adapter(ICourseInstance)
@interface.implementer(ICourseKeywords)
def _course_keywords(context):
    get_course_vendor_info(context, create=False)
    return _Keywords()
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

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import find_interface


@component.adapter(ICourseDiscussion)
@interface.implementer(ICourseInstance)
def _course_discussion_to_course(context):
    return find_interface(context, ICourseInstance, strict=False)


@component.adapter(ICourseDiscussions)
@interface.implementer(ICourseInstance)
def _course_discussions_to_course(context):
    return find_interface(context, ICourseInstance, strict=False)

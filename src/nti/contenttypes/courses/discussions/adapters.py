#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseDiscussion)
@interface.implementer(ICourseInstance)
def _course_discussion_to_course(context):
    return find_interface(context, ICourseInstance, strict=False)


@component.adapter(ICourseDiscussions)
@interface.implementer(ICourseInstance)
def _course_discussions_to_course(context):
    return find_interface(context, ICourseInstance, strict=False)

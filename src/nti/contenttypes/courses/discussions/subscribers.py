#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.discussions.model import discussions_for_course

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _on_course_removed(course, unused_event=None):
    container = discussions_for_course(course, False)
    if container:
        logger.info('Removing course discussion(s) for %s', course)
        container.clear()

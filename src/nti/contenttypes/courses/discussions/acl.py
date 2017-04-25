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

from zope.cachedescriptors.property import Lazy

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_course_editors

from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IACLProvider

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces


@component.adapter(ICourseDiscussion)
@interface.implementer(IACLProvider)
class CourseDiscussionACLProvider(object):

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        # See comments in nti.dataserver.authorization_acl:has_permission
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
                ace_allowing(ROLE_CONTENT_ADMIN, ALL_PERMISSIONS, type(self))]

        course = ICourseInstance(self.context, None)
        if course is not None:
            for i in course.instructors or ():
                aces.append(ace_allowing(i, ACT_READ, type(self)))

            for e in get_course_editors(course):
                aces.append(ace_allowing(e, ACT_READ, type(self)))

        return acl_from_aces(aces)

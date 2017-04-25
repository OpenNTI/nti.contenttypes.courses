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

from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IACLProvider


@interface.implementer(IACLProvider)
@component.adapter(ICourseGradingPolicy)
class GradingPolicyACLProvider(object):

    def __init__(self, context):
        self.context = context

    @Lazy
    def __acl__(self):
        course = ICourseInstance(self.context)
        aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
                ace_allowing(ROLE_CONTENT_ADMIN, ALL_PERMISSIONS, type(self))]

        for i in course.instructors or ():
            aces.append(ace_allowing(i, ALL_PERMISSIONS, type(self)))

        for subinstance in get_course_subinstances(course):
            aces.extend(ace_allowing(i, ACT_READ, type(self))
                        for i in subinstance.instructors or ())

        # Now our content editors/admins.
        for editor in get_course_editors(course):
            aces.append(ace_allowing(editor, ALL_PERMISSIONS, type(self)))

        result = acl_from_aces(aces)
        return result

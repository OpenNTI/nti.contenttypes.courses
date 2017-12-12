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

from zope.cachedescriptors.property import readproperty

from nti.contenttypes.courses import MessageFactory as _

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import IJoinCourseInvitationActor

from nti.contenttypes.courses.interfaces import CourseNotFoundException
from nti.contenttypes.courses.interfaces import AlreadyEnrolledException
from nti.contenttypes.courses.interfaces import CourseCatalogUnavailableException

from nti.contenttypes.courses.utils import get_enrollment_in_hierarchy

from nti.invitations.model import Invitation

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.property.property import alias

from nti.schema.fieldproperty import createDirectFieldProperties

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IJoinCourseInvitation)
class JoinCourseInvitation(Invitation):
    createDirectFieldProperties(IJoinCourseInvitation)

    mimeType = mime_type = "application/vnd.nextthought.joincourseinvitation"

    entry = alias('course')

    @readproperty
    def scope(self):
        return ES_PUBLIC

    @readproperty
    def name(self):
        return self.receiver

    @readproperty
    def email(self):
        return self.receiver


@interface.implementer(IJoinCourseInvitationActor)
class JoinCourseInvitationActor(object):

    def __init__(self, invitation=None):
        self.invitation = invitation

    def accept(self, user, invitation=None):
        invitation = self.invitation if invitation is None else invitation
        entry = invitation.course
        scope = invitation.scope or ES_PUBLIC
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is None:
            raise CourseCatalogUnavailableException()

        # find course
        course = find_object_with_ntiid(entry)
        if course is None:
            course = catalog.getCatalogEntry(entry)

        course = ICourseInstance(course, None)
        if course is None:
            raise CourseNotFoundException()

        record = get_enrollment_in_hierarchy(course, user)
        if record is not None:
            msg = _(u"You are already enrolled in this course.")
            raise AlreadyEnrolledException(msg)

        enrollment_manager = ICourseEnrollmentManager(course)
        # pylint: disable=redundant-keyword-arg
        enrollment_manager.enroll(user, scope=scope)
        return True

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.coremetadata.interfaces import SYSTEM_USER_ID
from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BoardObjectsMixin
from nti.dataserver.metadata.predicates import BasePrincipalObjects

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments


def course_collector():
    catalog = component.getUtility(ICourseCatalog)
    for entry in catalog.iterCatalogEntries():
        course = ICourseInstance(entry, None)
        if course is not None:
            yield course


def outline_nodes_collector(course):
    result = []
    try:
        def _recurse(node):
            result.append(node)
            for child in node.values():
                _recurse(child)
        _recurse(course.Outline)
    except AttributeError:
        pass
    return result


@component.adapter(ISystemUserPrincipal)
class _CoursePrincipalObjects(BasePrincipalObjects, BoardObjectsMixin):

    system = (None, SYSTEM_USER_ID, SYSTEM_USER_NAME)

    def board_objects(self, board):
        generator = super(_CoursePrincipalObjects, self).board_objects(board)
        for item in generator:
            if self.creator(item) in self.system:
                yield item

    def iter_objects(self):
        result = []
        for course in course_collector():
            result.append(course)
            result.append(course.SharingScopes)
            result.extend(course.SharingScopes.values())
            result.extend(outline_nodes_collector(course))
            result.extend(self.board_objects(course.Discussions))
        return result


@component.adapter(IUser)
class _EnrollmentPrincipalObjects(BasePrincipalObjects, BoardObjectsMixin):

    def iter_objects(self):
        result = []
        for enrollments in component.subscribers((self.user,),
                                                 IPrincipalEnrollments):
            result.extend(enrollments.iter_enrollments())
        return result


@component.adapter(IUser)
class _UserBoardPrincipalObjects(BasePrincipalObjects, BoardObjectsMixin):

    def board_objects(self, board):
        username = self.user.username.lower()
        for item in super(_UserBoardPrincipalObjects, self).board_objects(board):
            if self.creator(item) == username:
                yield item

    def iter_objects(self):
        result = []
        for course in course_collector():
            enrollments = ICourseEnrollments(course)
            if enrollments.is_principal_enrolled(self.user):
                result.extend(self.board_objects(course.Discussions))
        return result

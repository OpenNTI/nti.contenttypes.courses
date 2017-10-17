#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BoardObjectsMixin
from nti.dataserver.metadata.predicates import BasePrincipalObjects

from nti.contenttypes.courses.utils import get_parent_course

logger = __import__('logging').getLogger(__name__)


def course_collector():
    catalog = component.queryUtility(ICourseCatalog)
    if catalog is not None:
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

    def board_objects(self, board):
        for item in super(_CoursePrincipalObjects, self).board_objects(board):
            if self.is_system_username(self.creator(item)):
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
        for item in super(_UserBoardPrincipalObjects, self).board_objects(board):
            if self.creator(item) == self.username:
                yield item

    def iter_objects(self):
        result = []
        for course in course_collector():
            enrollments = ICourseEnrollments(course)
            if enrollments.is_principal_enrolled(self.user):
                result.extend(self.board_objects(course.Discussions))
                parent = get_parent_course(course)
                if parent is not course:
                    result.extend(self.board_objects(parent.Discussions))
        return result

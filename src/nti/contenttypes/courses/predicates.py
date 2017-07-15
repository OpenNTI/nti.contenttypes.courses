#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BasePrincipalObjects

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
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
class _CoursePrincipalObjects(BasePrincipalObjects):

    def iter_objects(self):
        result = []
        for course in course_collector():
            result.append(course)
            for node in outline_nodes_collector(course):
                result.append(node)
        return result


@component.adapter(IUser)
class _EnrollmentPrincipalObjects(BasePrincipalObjects):

    def iter_objects(self):
        result = []
        for enrollments in component.subscribers((self.user,),
                                                 IPrincipalEnrollments):
            for enrollment in enrollments.iter_enrollments():
                result.append(enrollment)
        return result

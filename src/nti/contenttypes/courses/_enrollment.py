#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.contenttypes.courses.enrollment import check_enrollment_mapped
from nti.contenttypes.courses.enrollment import has_deny_open_enrollment
from nti.contenttypes.courses.enrollment import check_deny_open_enrollment

from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IDenyOpenEnrollment
from nti.contenttypes.courses.interfaces import IEnrollmentMappedCourseInstance

from nti.contenttypes.courses.utils import get_parent_course

logger = __import__('logging').getLogger(__name__)


def set_deny_open_enrollment(course, deny):
    entry = ICourseCatalogEntry(course)
    if deny:
        if not IDenyOpenEnrollment.providedBy(course):
            interface.alsoProvides(entry, IDenyOpenEnrollment)
            interface.alsoProvides(course, IDenyOpenEnrollment)
    elif IDenyOpenEnrollment.providedBy(course):
        interface.noLongerProvides(entry, IDenyOpenEnrollment)
        interface.noLongerProvides(course, IDenyOpenEnrollment)


def update_deny_open_enrollment(course):
    if not ICourseSubInstance.providedBy(course):
        reference = course
    else:
        if has_deny_open_enrollment(course):
            reference = course
        else:
            # inherit from parent
            reference = get_parent_course(course)
    deny = check_deny_open_enrollment(reference)
    set_deny_open_enrollment(course, deny)


def check_enrollment_mapped_course(course):
    if not ICourseSubInstance.providedBy(course):  # only parent course
        if check_enrollment_mapped(course):
            interface.alsoProvides(course, IEnrollmentMappedCourseInstance)
        else:
            interface.noLongerProvides(course, IEnrollmentMappedCourseInstance)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.site.interfaces import IHostPolicyFolder

logger = __import__('logging').getLogger(__name__)


def get_course_packages(context):
    course = ICourseInstance(context, None)
    if course is not None:
        try:
            packs = course.ContentPackageBundle.ContentPackages or ()
        except AttributeError:
            try:
                packs = (course.legacy_content_package,)
            except AttributeError:
                packs = ()
        return packs or ()
    return ()
get_course_content_packages = get_course_packages


def get_course_content_units(context):
    content_units = []

    def _recur(content_unit, accum):
        accum.append(content_unit)
        for child in content_unit.children or ():
            _recur(child, accum)

    for packag in get_course_packages(context):
        _recur(packag, content_units)
    return content_units


def get_course_site_name(context):
    folder = IHostPolicyFolder(ICourseInstance(context, None), None)
    return folder.__name__ if folder is not None else None
get_course_site = get_course_site_name


def get_course_site_registry(context):
    course = ICourseInstance(context, None)
    folder = IHostPolicyFolder(course, None)
    # pylint: disable=too-many-function-args
    return folder.getSiteManager() if folder is not None else None

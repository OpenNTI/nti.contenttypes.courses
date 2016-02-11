#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.contenttypes.courses.interfaces import ICourseInstance

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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

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

def get_course_site_name(context):
	course = ICourseInstance(context, None)
	folder = find_interface(course, IHostPolicyFolder, strict=False)
	return folder.__name__ if folder is not None else None
get_course_site = get_course_site_name

def get_course_site_registry(context):
	course = ICourseInstance(context, None)
	folder = find_interface(course, IHostPolicyFolder, strict=False)
	return folder.getSiteManager() if folder is not None else None

def is_part_auto_gradable(part):
	# Validate every part has grader.
	result = 	getattr(part, 'grader_interface', None) \
			or  getattr(part, 'grader_name', None)
	return bool(result)

def can_be_auto_graded(assignment):
	for part in assignment.parts or ():
		question_set = part.question_set
		for question in question_set.questions or ():
			for part in question.parts or ():
				if not is_part_auto_gradable(part):
					return False
	return True

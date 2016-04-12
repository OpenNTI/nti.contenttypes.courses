#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
from urllib import unquote
from urlparse import urlparse

from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE
from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE_REF

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import SECTIONS
from nti.contenttypes.courses.interfaces import DISCUSSIONS
from nti.contenttypes.courses.interfaces import ENROLLMENT_LINEAGE_MAP

from nti.contenttypes.courses.utils import get_parent_course

from nti.ntiids.ntiids import make_specific_safe

ENROLLED_COURSE_ROOT = ':EnrolledCourseRoot'
ENROLLED_COURSE_SECTION = ':EnrolledCourseSection'

def get_discussion_id(discussion):
	result = getattr(discussion, 'id', discussion)
	return result

def is_nti_course_bundle(discussion):
	iden = get_discussion_id(discussion)
	parts = urlparse(iden) if iden else None
	result = NTI_COURSE_BUNDLE == parts.scheme if parts else False
	return result

def get_discussion_path(discussion):
	iden = get_discussion_id(discussion)
	if is_nti_course_bundle(iden):
		result = iden[len(NTI_COURSE_BUNDLE_REF) - 1:]
		return result
	return None

def get_discussion_key(discussion):
	iden = get_discussion_id(discussion)
	if is_nti_course_bundle(iden):
		parts = urlparse(iden)
		result = os.path.split(unquote(parts.path))
		return result[1]
	return None

def get_discussion_mapped_scopes(discussion):
	result = set()
	for scope in discussion.scopes:
		result.update(ENROLLMENT_LINEAGE_MAP.get(scope) or ())
	return result

def get_course_for_discussion(discussion, context):
	iden = get_discussion_id(discussion)
	if is_nti_course_bundle(iden) and context is not None:
		parent = get_parent_course(context)
		if parent is not None:
			path = get_discussion_path(iden)
			splits = path.split(os.path.sep)
			if SECTIONS in splits:  # e.g. /Sections/02/Discussions
				return parent.SubInstances.get(splits[2]) if len(splits) >= 3 else None
			else:
				return parent
	return None

def get_discussion_for_path(path, context):
	path = os.path.sep + path if not path.startswith(os.path.sep) else os.path.sep
	parent = get_parent_course(context)
	if parent is not None:
		splits = path.split(os.path.sep)
		if SECTIONS in splits and len(splits) >= 2 and splits[1] == SECTIONS:  # e.g. /Sections/02/Discussions/p.json
			course = parent.SubInstances.get(splits[2]) if len(splits) >= 3 else None
			course = None if len(splits) < 3 or DISCUSSIONS != splits[3] else course
			name = splits[4] if len(splits) >= 5 else None
		else:
			course = parent  # e.g. /Discussions/p.json
			course = None if len(splits) < 2 or DISCUSSIONS != splits[1] else course
			name = splits[2] if len(splits) >= 3 else None

		if course is not None and name:
			discussions = ICourseDiscussions(course, None) or {}
			for prefix in (name, name.replace(' ', '_')):
				result = discussions.get(prefix) or discussions.get(prefix + '.json')
				if result is not None:
					break
			return result
	return None

def get_topic_key(discussion):
	__traceback_info__ = discussion
	if is_nti_course_bundle(discussion):
		name = get_discussion_path(discussion)
	else:
		name = discussion.title
		if not name:
			name = u''
		elif not isinstance(name, unicode):
			name = name.decode('utf-8', 'ignore')
	name = make_specific_safe(name)
	return name

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

from ..interfaces import SECTIONS
from ..interfaces import ENROLLMENT_LINEAGE_MAP

from ..interfaces import ICourseInstance
from ..interfaces import ICourseSubInstance

from .interfaces import NTI_COURSE_BUNDLE
from .interfaces import NTI_COURSE_BUNDLE_REF

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

def get_parent_course(context):
	context = ICourseInstance(context, None)
	if ICourseSubInstance.providedBy(context):
		parent = context.__parent__.__parent__
	elif context is not None:
		parent = context
	return parent

def get_course_for_discussion(discussion, context):
	iden = get_discussion_id(discussion)
	if is_nti_course_bundle(iden) and context is not None:
		parent = get_parent_course(context)
		if parent is not None:
			parts = iden[len(NTI_COURSE_BUNDLE_REF):] 
			splits = parts.split('/')
			if SECTIONS in splits:  # e.g. Sections/02/Discussions
				return parent.SubInstances.get(splits[1]) if len(splits) >= 2 else None
			else:
				return parent
	return None

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

from zope import component

from ..interfaces import ENROLLMENT_LINEAGE_MAP

from ..interfaces import ICourseCatalog

from .interfaces import NTI_COURSE_BUNDLE

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

def get_discussion_provider(discussion):
	iden = get_discussion_id(discussion)
	if is_nti_course_bundle(iden):
		parts = urlparse(iden)
		result = unquote(parts.netloc)
		return result
	return None

def get_discussion_key(discussion):
	iden = get_discussion_id(discussion)
	if is_nti_course_bundle(iden):
		parts = urlparse(iden)
		result = os.path.split(unquote(parts.path))
		return result[1]
	return None

def get_entry_for_discussion(discussion, catalog=None, registry=component):
	provider = get_discussion_provider(discussion)
	catalog = registry.queryUtility(ICourseCatalog) if catalog is None else catalog
	if provider and catalog is not None:
		for entry in catalog.iterCatalogEntries():
			if entry.ProviderUniqueID == provider:
				return entry
	return None

def get_discussion_scopes(discussion):
	result = set()
	for scope in discussion.scopes:
		result.update(ENROLLMENT_LINEAGE_MAP.get(scope) or ())
	return result


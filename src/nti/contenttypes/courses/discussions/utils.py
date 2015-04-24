#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urllib import unquote
from urlparse import urlparse

from zope import component

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import make_specific_safe

from ..interfaces import ES_ALL
from ..interfaces import ES_PUBLIC
from ..interfaces import ENROLLMENT_LINEAGE_MAP
from ..interfaces import ENROLLMENT_SCOPE_NAMES

from ..interfaces import ICourseCatalog

from .interfaces import NTI_COURSE_BUNDLE

ENROLLED_COURSE_ROOT = ':EnrolledCourseRoot'
ENROLLED_COURSE_SECTION = ':EnrolledCourseSection'

def is_nti_course_bundle(discussion):
	parts = urlparse(discussion.id) if discussion.id else None
	result = NTI_COURSE_BUNDLE == parts.scheme if parts else False
	return result

def get_discussion_provider(discussion):
	if is_nti_course_bundle(discussion):
		parts = urlparse(discussion.id)
		result = unquote(parts.netloc)
		return result
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
	scopes = set()
	for scope in discussion.scopes:
		scopes.update(ENROLLMENT_LINEAGE_MAP.get(scope) or ())
	return scopes

def get_topics_ntiids(discussion, is_section=False, provider=None, base=None):
	if not provider and not base:
		raise ValueError( 'Must supply provider' )
	
	result = {}
	is_ncb = is_nti_course_bundle(discussion)
	if is_ncb:
		type_postfix = u''
		ncb_specific = discussion.id[len(NTI_COURSE_BUNDLE) + 3:]
		ncb_specific = make_specific_safe(ncb_specific)
	else:
		ncb_specific = make_specific_safe(discussion.title)
		type_postfix = ENROLLED_COURSE_SECTION if is_section else ENROLLED_COURSE_ROOT
		
	provider = make_provider_safe(provider or get_provider(base))
	if ES_ALL in discussion.scopes:
		scopes = ENROLLMENT_SCOPE_NAMES
	else:
		scopes = set(discussion.scopes)
		
	for scope in scopes:
		key = scope
		scope = 'Open' if scope == ES_PUBLIC else scope
		nttype = 'Topic%s' % type_postfix
		pre_spec = '%s%s' % (scope, (u'' if is_ncb else '_Discussions') )
		specific = make_specific_safe("%s_%s" % (pre_spec, ncb_specific))
		ntiid = make_ntiid(provider=provider, nttype=nttype, specific=specific, base=base)
		result[key] = ntiid
	return result
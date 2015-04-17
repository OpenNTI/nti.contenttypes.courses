#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urlparse import urlparse

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import make_specific_safe

from ..interfaces import ENROLLMENT_SCOPE_VOCABULARY

from .interfaces import ALL
from .interfaces import NTI_COURSE_BUNDLE

ENROLLED_COURSE_ROOT = ':EnrolledCourseRoot'
ENROLLED_COURSE_SECTION = ':EnrolledCourseSection'
ALL_SCOPES = tuple(x.value for x in ENROLLMENT_SCOPE_VOCABULARY)

def get_topics_ntiids(discussion, is_section=False, provider=None, base=None):
	assert discussion.id
	if not provider and not base:
		raise ValueError( 'Must supply provider' )
	
	result = {}
	
	parts = urlparse(discussion.id)
	is_ncb = NTI_COURSE_BUNDLE == parts.scheme
	if is_ncb:
		type_postfix = u''
		ncb_specific = discussion.id[len(NTI_COURSE_BUNDLE) + 3:]
		ncb_specific = make_specific_safe(ncb_specific)
	else:
		ncb_specific = make_specific_safe(discussion.title)
		type_postfix = ENROLLED_COURSE_SECTION if is_section else ENROLLED_COURSE_ROOT
		
	provider = make_provider_safe(provider or get_provider(base))
	if ALL in discussion.scopes:
		scopes = ALL_SCOPES
	else:
		scopes = set(discussion.scopes)
		
	for scope in scopes:
		pre_spec = '%s_Discussions' % scope
		nttype = 'Topic%s' % type_postfix
		specific = make_specific_safe("%s_%s" % (pre_spec, ncb_specific))
		ntiid = make_ntiid(provider=provider, nttype=nttype, specific=specific, base=base)
		result[scope] = ntiid
	return result

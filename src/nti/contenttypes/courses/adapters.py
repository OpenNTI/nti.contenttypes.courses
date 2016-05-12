#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
from collections import Mapping

from zope import component
from zope import interface

from zope.traversing.api import traverse

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseKeywords

from nti.contenttypes.courses.utils import get_course_vendor_info

class _Keywords(object):

	__slots__ = (b'keywords',)

	def __init__(self, keywords=()):
		self.keywords = keywords

def _keyword_gatherer(data):
	result = set()
	if isinstance(data, six.string_types):
		result.update(data.split())
	elif isinstance(data, (list, tuple, set)):
		for value in data:
			result.update(_keyword_gatherer(value))
	elif isinstance(data, Mapping):
		for key, value in data.items():
			result.add(key)
			result.update(_keyword_gatherer(value))
	elif data is not None:
		result.add(str(data))
	result = tuple(x.strip().lower() for x in result if x)
	return result

def _invitation_gatherer(data):
	result = set()
	if isinstance(data, six.string_types):
		result.update(data.split())
	elif isinstance(data, (list, tuple, set)):
		for value in data:
			if isinstance(value, six.string_types):
				result.add(value)
			elif isinstance(value, Mapping):
				code = value.get('code') or value.get('Code')
				result.add(code)
	result = tuple(x.strip().lower() for x in result if x)
	return result

@component.adapter(ICourseInstance)
@interface.implementer(ICourseKeywords)
def _course_keywords(context):
	result = set()
	data = get_course_vendor_info(context, create=False) or {}
	data = traverse(data, 'NTI/Keywords', default=None)
	result.update(_keyword_gatherer(data))
	data = traverse(data, 'NTI/Tags', default=None)
	result.update(_keyword_gatherer(data))
	data = traverse(data, 'NTI/Invitations', default=None)
	result.update(_invitation_gatherer(data))
	result.discard(u'')
	return _Keywords(sorted(result))

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

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseKeywords

from nti.contenttypes.courses.utils import get_course_vendor_info

from nti.ntiids.ntiids import make_specific_safe

class _Keywords(object):

	__slots__ = (b'keywords',)

	def __init__(self, keywords=()):
		self.keywords = keywords

def _keyword_gatherer(data):
	result = set()
	if isinstance(data, six.string_types):
		result.update(data.split())
	elif isinstance(data, (list, tuple)):
		for value in data:
			result.update(_keyword_gatherer(value))
	elif isinstance(data, Mapping):
		for key, value in data.items():
			result.add(key)
			result.update(_keyword_gatherer(value))
	elif data is not None:
		result.add(str(data))
	result = tuple(x.strip() for x in result if x)
	return result

def _invitation_gatherer(data):
	result = set()
	if isinstance(data, six.string_types):
		result.update(data.split())
	elif isinstance(data, (list, tuple)):
		for value in data:
			if isinstance(value, six.string_types):
				result.add(value)
			elif isinstance(value, Mapping):
				code = value.get('code') or value.get('Code')
				result.add(code)
	result = tuple(x.strip() for x in result if x)
	return result

def _paths(course):
	o = course
	raw = []
	safe = []
	while o is not None and not ICourseCatalog.providedBy(o):
		try:
			raw.append(o.__name__)
			safe.append(make_specific_safe(o.__name__))
			o = o.__parent__
		except AttributeError:
			break
	result = {raw[-1], raw[0]} # admin level & section/name
	for p in (raw, safe):
		p.reverse()
		result.add('/'.join(p))
	return tuple(result)

@component.adapter(ICourseInstance)
@interface.implementer(ICourseKeywords)
def _course_keywords(context):
	result = set()
	info = get_course_vendor_info(context, create=False) or {}
	# keyword and tags
	for path in ('NTI/Keywords', 'NTI/Tags'):
		data = traverse(info, path, default=None)
		result.update(_keyword_gatherer(data))
	# invitation codes
	data = traverse(info, 'NTI/Invitations', default=None)
	result.update(_invitation_gatherer(data))
	# paths
	result.update(_paths(ICourseInstance(context, None)))
	# clean and return
	result.discard(u'')
	result.discard(None)
	return _Keywords(sorted(result))

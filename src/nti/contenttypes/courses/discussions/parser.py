#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

import simplejson

from zope import component
from zope import lifecycleevent

from zope.intid import IIntIds

from nti.contentlibrary.bundle import BUNDLE_META_NAME
from nti.contentlibrary.interfaces import IDelimitedHierarchyKey
from nti.contentlibrary.interfaces import IDelimitedHierarchyBucket
from nti.contentlibrary.synchronize import SynchronizationException

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from .interfaces import NTI_COURSE_BUNDLE
from .interfaces import ICourseDiscussions

INVALID_DISCUSSION_CODE = 300

class InvalidDiscussionException(SynchronizationException):
	code = INVALID_DISCUSSION_CODE

def path_to_course(resource):
	result = []
	while resource is not None:
		if 	IDelimitedHierarchyBucket.providedBy(resource) and \
			resource.getChildNamed(BUNDLE_META_NAME):
			break
		try:
			result.append(resource.__name__)
			resource = resource.__parent__
		except AttributeError:
			resource = None
	result.reverse()
	result = os.path.sep.join(result)
	return result

def prepare_json_text(s):
	result = unicode(s, 'utf-8') if isinstance(s, bytes) else s
	return result

def parse_discussions(course, bucket, intids=None):
	__traceback_info__ = bucket, course
	discussions = ICourseDiscussions(course)

	result = False
	child_files = dict()
	for item in bucket.enumerateChildren():
		if IDelimitedHierarchyKey.providedBy(item):
			child_files[item.__name__] = item

	# Remove anything the discussions has that aren't on the filesystem
	for child_name in list(discussions):
		if child_name not in child_files:
			logger.info("Removing discussion %s (%r)", child_name,
						 discussions[child_name])
			del discussions[child_name]
			result = True

	intids = component.queryUtility(IIntIds) if intids is None else intids
	for name, key in child_files.items():
		discussion = discussions.get(name)
		if discussion is not None and key.lastModified <= discussion.lastModified:
			continue

		json = simplejson.loads(prepare_json_text(key.readContents()))
		factory = find_factory_for(json)
		if factory is None:
			raise InvalidDiscussionException(
					"Cannot find factory for discussion in json file. Check MimeType")
		new_discussion = factory() if discussion is None else discussion
		update_from_external_object(new_discussion, json, notify=False)

		path = path_to_course(key)
		new_discussion.id = "%s://%s" % (NTI_COURSE_BUNDLE, path)
		if discussion is None:
			lifecycleevent.created(new_discussion)
			discussions[name] = new_discussion
		else:
			discussions._p_changed = True
			discussions.updateLastMod()
			lifecycleevent.modified(new_discussion)

		# set to key last modified
		new_discussion.lastModified = key.lastModified
		result = True
	return result

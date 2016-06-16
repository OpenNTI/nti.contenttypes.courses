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

from zope import lifecycleevent

from nti.contentlibrary.interfaces import IDelimitedHierarchyKey
from nti.contentlibrary.synchronize import SynchronizationException

from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import SECTIONS 
from nti.contenttypes.courses.interfaces import DISCUSSIONS
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

INVALID_DISCUSSION_CODE = 300

class InvalidDiscussionException(SynchronizationException):
	code = INVALID_DISCUSSION_CODE

def path_to_discussions(course):
	if ICourseSubInstance.providedBy(course):
		path = "%s/%s/%s" % (SECTIONS, course.__name__, DISCUSSIONS)
	else:
		path = DISCUSSIONS
	return path

def prepare_json_text(s):
	result = unicode(s, 'utf-8') if isinstance(s, bytes) else s
	return result

def load_discussion(name, source, discussions, path, discussion=None):
	if hasattr(source, "read"):
		json = simplejson.loads(prepare_json_text(source.read()))
	elif hasattr(source, "readContents"):
		json = simplejson.loads(prepare_json_text(source.readContents()))
	else:
		json = simplejson.loads(prepare_json_text(source))
	factory = find_factory_for(json)
	if factory is None:
		raise InvalidDiscussionException(
				"Cannot find factory for discussion in json file. Check MimeType")
	new_discussion = factory() if discussion is None else discussion
	update_from_external_object(new_discussion, json, notify=False)

	# set discusion course bundle id before firing events
	path = os.path.join(path, name)
	new_discussion.id = "%s://%s" % (NTI_COURSE_BUNDLE, path)

	if discussion is None:
		lifecycleevent.created(new_discussion)
		discussions[name] = new_discussion
	else:
		discussions._p_changed = True
		discussions.updateLastMod()
		lifecycleevent.modified(new_discussion)
	return new_discussion

def parse_discussions(course, bucket, force=False, *args, **kwargs):
	__traceback_info__ = bucket, course
	discussions = ICourseDiscussions(course)

	result = False
	child_files = dict()
	for item in bucket.enumerateChildren():
		if IDelimitedHierarchyKey.providedBy(item):
			child_files[item.__name__] = item

	# Remove anything the discussions has that aren't on the filesystem
	for child_name in list(discussions): # snapshot
		if child_name not in child_files:
			logger.info("Removing discussion %s (%r)", child_name,
						discussions[child_name])
			del discussions[child_name]
			result = True

	for name, key in child_files.items():
		discussion = discussions.get(name)
		if 		not force \
			and discussion is not None \
			and key.lastModified <= discussion.lastModified:
			continue

		# parse and discussion
		__traceback_info__ = name, key
		discussion = load_discussion(name,
									 key.readContents(),
									 discussions,
									 discussion=discussion,
									 path=path_to_discussions(course))
		# set last mod from key
		discussion.lastModified = key.lastModified
		result = True
	return result

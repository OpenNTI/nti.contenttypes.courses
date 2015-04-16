#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.intid

from zope import component

from zope import lifecycleevent

from zope.location.location import locate

from ZODB.interfaces import IConnection

from nti.contentlibrary.interfaces import IDelimitedHierarchyKey

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from .interfaces import ICourseDiscussions

def parse_discussions(course, bucket):
	discussions = ICourseDiscussions(course)
	intids = component.queryUtility( zope.intid.IIntIds )
	if intids is None:
		return
		
	__traceback_info__ = bucket, course

	child_files = dict()
	for item in bucket.enumerateChildren():
		if IDelimitedHierarchyKey.providedBy(item):
			child_files[item.__name__] = item

	## Remove anything the discussions has that aren't on the filesystem
	for child_name in list(discussions):
		if child_name not in child_files:
			logger.info("Removing discussion %s (%r)", child_name,
						 discussions[child_name])
			del discussions[child_name]
		
	for name, key  in child_files.items():
		discussion = discussions.get(name)
		if discussion is not None and key.lastModified <= discussion.lastModified:
			continue

		json = key.readContentsAsYaml()
		factory = find_factory_for(json)
		new_discussion = factory()
		update_from_external_object(new_discussion, json)
	
		if discussion is None:
			lifecycleevent.created(new_discussion)
			discussions[name] = new_discussion
		else:
			## remove an unregister all w/o event
			discussions._delitemf(name, event=False)
			intids.unregister(discussion)
			
			## add new object w/o event
			discussions._setitemf(name, new_discussion)
			locate(new_discussion, parent=discussions, name=key)
			IConnection(discussions).add(new_discussion)
			intids.register(new_discussion)
			discussions._p_changed = True
			discussions.updateLastMod()
			
			## notify
			lifecycleevent.modified(new_discussion)

		## set to key last modified
		new_discussion.lastModified = key.lastModified

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import lifecycleevent

from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo

from nti.dataserver.users.interfaces import IAvatarURL
from nti.dataserver.users.interfaces import IBackgroundURL
from nti.dataserver.users.interfaces import IFriendlyNamed

def update_sharing_scopes_friendly_names(course):
	result = []
	entry = ICourseCatalogEntry(course)
	sharing_scopes_data = (ICourseInstanceVendorInfo(course)
							.get('NTI', {})
							.get("SharingScopesDisplayInfo", {}))
	for scope in course.SharingScopes.values():
		scope_name = scope.__name__
		sharing_scope_data = sharing_scopes_data.get(scope_name, {})

		friendly_scope = IFriendlyNamed(scope)
		friendly_title = ENROLLMENT_SCOPE_VOCABULARY.getTerm(scope_name).title

		if sharing_scope_data.get('alias'):
			alias = sharing_scope_data['alias']
		elif entry.ProviderUniqueID:
			alias = entry.ProviderUniqueID + ' - ' + friendly_title
		else:
			alias = friendly_scope.alias

		if sharing_scope_data.get('realname'):
			realname = sharing_scope_data['realname']
		elif entry.title:
			realname = entry.title + ' - ' + friendly_title
		else:
			realname = friendly_scope.realname

		modified_scope = False
		if (realname, alias) != (friendly_scope.realname, friendly_scope.alias):
			friendly_scope.realname = realname
			friendly_scope.alias = alias
			lifecycleevent.modified(friendly_scope)
			modified_scope = True

		def _imageURL(scope, image_iface, image_attr):
			image_attr = str( image_attr )
			result = False
			scope_imageURL = getattr(scope, image_attr, None)
			inputed_imageURL = sharing_scope_data.get(image_attr, None)
			if inputed_imageURL:
				if scope_imageURL != inputed_imageURL:
					logger.info("Adjusting scope %s %s to %s for course %s",
								scope_name, image_attr, inputed_imageURL, entry.ntiid)
					interface.alsoProvides(scope, image_iface)
					setattr(scope, image_attr, inputed_imageURL)
					result = True
			else:
				removed = False
				if hasattr(scope, image_attr):
					removed = True
					delattr(scope, image_attr)
					result = True
				if image_iface.providedBy(scope):
					removed = True
					interface.noLongerProvides(scope, image_iface)
					result = True
				if removed:
					logger.warn("Scope %s %s was removed for course %s",
								 scope_name, image_attr, entry.ntiid)
			return result

		modified_scope = _imageURL(scope, IAvatarURL, 'avatarURL') or modified_scope
		modified_scope = _imageURL(scope, IBackgroundURL, 'backgroundURL') or modified_scope

		if modified_scope:
			result.append(scope)
			lifecycleevent.modified(scope)
	return tuple(result)

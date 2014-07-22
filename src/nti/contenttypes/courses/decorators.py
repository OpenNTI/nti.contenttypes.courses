#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Externalization decorators.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.dataserver.interfaces import IEntityContainer
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.externalization.externalization import to_external_object

# XXX: JAM: Don't like this dependency here. Refactor for zope.security interaction
# support
from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
CLASS = StandardExternalFields.CLASS

@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseInstance)
class _SharingScopesAndDiscussionDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _do_decorate_external(self, context, result):
		if ICourseSubInstance.providedBy(context):
			# conflated, yes, but simpler
			parent = context.__parent__.__parent__
			if parent is not None:
				self._do_decorate_external(parent, result)
				result['ParentSharingScopes'] = result['SharingScopes']
				result['ParentDiscussions'] = to_external_object(parent.Discussions,
																 request=self.request)

		scopes = context.SharingScopes
		ext_scopes = LocatedExternalDict()
		ext_scopes.__parent__ = scopes.__parent__
		ext_scopes.__name__ = scopes.__name__

		ext_scopes[CLASS] = 'CourseInstanceSharingScopes'

		user = self.remoteUser

		for name, scope in scopes.items():
			if user in IEntityContainer(scope):
				ext_scopes[name] = to_external_object(scope, request=self.request)

		result['SharingScopes'] = ext_scopes

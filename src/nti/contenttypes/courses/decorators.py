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

from urlparse import urljoin


from nti.dataserver.interfaces import IEntityContainer
from nti.externalization.interfaces import IExternalObjectDecorator
from .interfaces import ICourseInstance
from .interfaces import ICourseSubInstance
from .interfaces import ICourseCatalogEntry

from nti.externalization.externalization import to_external_object
from nti.externalization.singleton import SingletonDecorator
from nti.externalization.oids import to_external_ntiid_oid

# XXX: JAM: Don't like this dependency here. Refactor for zope.security interaction
# support
from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
CLASS = StandardExternalFields.CLASS

@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseInstance, interface.Interface)
class _SharingScopesAndDiscussionDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _do_decorate_external(self, context, result):
		if ICourseSubInstance.providedBy(context):
			# conflated, yes, but simpler
			parent = context.__parent__.__parent__
			if parent is not None:
				parent_result = {}
				self._do_decorate_external(parent, parent_result)
				result['ParentLegacyScopes'] = parent_result.get('LegacyScopes')
				result['ParentSharingScopes'] = parent_result['SharingScopes']
				result['ParentDiscussions'] = to_external_object(parent.Discussions,
																 request=self.request)

		scopes = context.SharingScopes
		if self._is_authenticated:
			ext_scopes = LocatedExternalDict()
			ext_scopes.__parent__ = scopes.__parent__
			ext_scopes.__name__ = scopes.__name__

			ext_scopes[CLASS] = 'CourseInstanceSharingScopes'

			user = self.remoteUser

			for name, scope in scopes.items():
				if user in IEntityContainer(scope):
					ext_scopes[name] = to_external_object(scope, request=self.request)

			result['SharingScopes'] = ext_scopes

		else:
			result['SharingScopes'] = to_external_object(scopes)

		# Legacy
		if 'LegacyScopes' not in result:
			ls = result['LegacyScopes'] = {}
			# You get public and restricted regardless of whether
			# you were enrolled in them...
			if 'Public' in scopes:
				ls['public'] = scopes['Public'].NTIID
			if 'ForCredit' in scopes:
				ls['restricted'] = scopes['ForCredit'].NTIID


@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseCatalogEntry)
class _LegacyCCEFieldDecorator(object):

	__metaclass__ = SingletonDecorator

	def _course_package(self, context):
		course = ICourseInstance(context, None)
		if course is not None:
			try:
				package = list(course.ContentPackageBundle.ContentPackages)[0]
			except (AttributeError,IndexError):
				package = None
		return course, package

	def decorateExternalObject(self, context, result):
		# All the possibly missing legacy fields hang off
		# an existing single content package. Can we get one of those?
		course = None
		package = None
		checked = False

		if 'ContentPackageNTIID' not in result:
			course, package = self._course_package(context)
			checked = True
			if package is not None:
				result['ContentPackageNTIID'] = package.ntiid

		if not result.get('LegacyPurchasableIcon') or not result.get('LegacyPurchasableThumbnail'):
			if not checked:
				course, package = self._course_package(context)
				checked = True

			if package is not None:
				# Copied wholesale from legacy code
				purch_id = context.ProviderUniqueID.replace(' ','').split('-')[0]
				if getattr(context, 'Term', ''): # non interface, briefly seen field
					purch_id += context.Term.replace(' ', '').replace('-', '')

				# We have to externalize the package to get correct URLs
				# to the course. They need to be absolute because there is no context
				# in the purchasable.
				ext_package = to_external_object( package )
				icon = urljoin( ext_package['href'],
								'images/' + purch_id + '_promo.png' )
				thumbnail = urljoin( ext_package['href'],
									 'images/' + purch_id + '_cover.png' )
				# Temporarily also stash these things on the entry itself too
				# where they can be externalized in the course catalog;
				# this should save us a trip through next time
				context.LegacyPurchasableIcon = icon
				context.LegacyPurchasableThumbnail = thumbnail

				result['LegacyPurchasableThumbnail'] = thumbnail
				result['LegacyPurchasableIcon'] = icon

		if 'CourseNTIID' not in result:
			if not checked:
				course, package = self._course_package(context)
				checked = True
			if course is not None:
				# courses themselves do not typically actually
				# have an identifiable NTIID and rely on the OID
				# (this might change with auto-creation of the catalogs now)
				try:
					result['CourseNTIID'] = course.ntiid
				except AttributeError:
					result['CourseNTIID'] = to_external_ntiid_oid(course)

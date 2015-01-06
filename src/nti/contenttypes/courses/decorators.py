#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Externalization decorators.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urlparse import urljoin

from zope import component
from zope import interface

# XXX: JAM: Don't like this dependency here. Refactor for zope.security interaction
# support
from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.dataserver.traversal import find_interface
from nti.dataserver.interfaces import IEntityContainer

from nti.externalization.oids import to_external_ntiid_oid
from nti.externalization.singleton import SingletonDecorator
from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.externalization import to_external_object
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.sharing import use_parent_default_sharing_scope

from nti.ntiids.ntiids import make_specific_safe

from .interfaces import ES_PUBLIC
from .interfaces import ES_CREDIT
from .interfaces import ES_PURCHASED
from .interfaces import ICourseInstance
from .interfaces import ICourseSubInstance
from .interfaces import ICourseCatalogEntry
from .interfaces import INonPublicCourseInstance
from .interfaces import ICourseInstanceScopedForum

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS

@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseInstance, interface.Interface)
class _SharingScopesAndDiscussionDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _do_decorate_external(self, context, result):
		is_section = ICourseSubInstance.providedBy(context)

		default_sharing_scope = None

		if is_section:
			# conflated, yes, but simpler
			parent = context.__parent__.__parent__
			if parent is not None:
				parent_result = {}
				self._do_decorate_external(parent, parent_result)
				result['ParentLegacyScopes'] = parent_result.get('LegacyScopes')
				result['ParentSharingScopes'] = parent_result['SharingScopes']
				result['ParentDiscussions'] = to_external_object(parent.Discussions,
																 request=self.request)
				if use_parent_default_sharing_scope( context ):
					default_sharing_scope = result['ParentSharingScopes']['DefaultSharingScopeNTIID']

		scopes = context.SharingScopes
		ext_scopes = LocatedExternalDict()
		ext_scopes.__name__ = scopes.__name__
		ext_scopes.__parent__ = scopes.__parent__

		ext_scopes[CLASS] = 'CourseInstanceSharingScopes'
		items = ext_scopes[ITEMS] = {}

		user = self.remoteUser if self._is_authenticated else None
		for name, scope in scopes.items():
			if user is None or user in IEntityContainer(scope):
				items[name] = to_external_object(scope, request=self.request)

		result['SharingScopes'] = ext_scopes

		# Legacy
		if 'LegacyScopes' not in result:
			ls = result['LegacyScopes'] = {}
			# Historically, you get public and restricted regardless of whether
			# you were enrolled in them...
			# Because we're talking specifically to legacy clients, we need to give them
			# something that makes sense in their flat view of the world; therefore,
			# if we're actually in a subinstance, we want public sharing to be TRULY
			# public, across everyone that might be enrolled in all sections. The exception
			# is if the parent course is non-open-enrollable (e.g., closed, or not being used
			# except for administration---one scenario had two sections that opened at different
			# dates); in that case, we want to use the parent if we can get it.
			if default_sharing_scope is not None:
				public = default_sharing_scope
			else:
				public = None
				parent = context.__parent__
				if 	(	is_section
					 and find_interface(parent, INonPublicCourseInstance, strict=False) is None
					 and 'public' in result.get('ParentLegacyScopes', ()) ):
					public = result['ParentLegacyScopes']['public']
				elif ES_PUBLIC in scopes:
					public = scopes[ES_PUBLIC].NTIID

			ls['public'] = public

			if ES_CREDIT in scopes:
				ls['restricted'] = scopes[ES_CREDIT].NTIID
			if ES_PURCHASED in scopes:
				ls['purchased'] = scopes[ES_PURCHASED].NTIID

		ls = result['LegacyScopes']

		if default_sharing_scope is None:
			# Point clients to what the should do by default.
			# For the default if you're not enrolled for credit, match what flat clients do.
			default_sharing_scope = ls['public']
			if user is not None:
				if ES_CREDIT in scopes and user in IEntityContainer(scopes[ES_CREDIT]):
					default_sharing_scope = ls.get('restricted')
				elif ES_PURCHASED in scopes and user in IEntityContainer(scopes[ES_PURCHASED]):
					default_sharing_scope = ls.get('purchased')

		result['SharingScopes']['DefaultSharingScopeNTIID'] = default_sharing_scope

@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseInstance, interface.Interface)
class _AnnouncementsDecorator(AbstractAuthenticatedRequestAwareDecorator):
	"""
	Adds announcement discussions to externalized course, by scope.
	"""

	def _in_scope(self, scope_name, course):
		user = self.remoteUser if self._is_authenticated else None
		scope = course.SharingScopes[scope_name]
		# In scope if we have user and they are in scope.
		return user is not None and user in IEntityContainer( scope )

	def _get_forum_key(self, forum_types, name, display_key):
		result = forum_types.get( display_key )
		if not result:
			# Replicate forum key logic used during create time
			result = make_specific_safe( name + ' ' + 'Announcements' )
		return result

	def _do_decorate_external(self, context, result):

		# First, get parent if we are a section.
		is_section = ICourseSubInstance.providedBy(context)

		if is_section:
			# conflated, yes, but simpler
			parent = context.__parent__.__parent__
			if parent is not None:
				parent_result = {}
				self._do_decorate_external(parent, parent_result)
				result['ParentAnnouncementForums'] = parent_result.get('AnnouncementForums')

		# A marker interface might make this easier
		announcements = {}
		items = { 	ITEMS: announcements,
					'Class': 'CourseInstanceAnnouncementForums' }

		vendor_info = ICourseInstanceVendorInfo( context )
		forum_types = vendor_info.get('NTI', {}).get('Forums', {})

		for scope_name, scope_term in ENROLLMENT_SCOPE_VOCABULARY.by_token.iteritems():
			name = scope_term.vendor_key
			key_prefix = scope_term.vendor_key_prefix

			has_key = 'Has' + key_prefix + 'Announcements'

			# They have announcements and we're in the scope
			if 		forum_types.get( has_key ) \
				and self._in_scope( scope_name, context ):
				# Ok, let's find our forum
				display_key = key_prefix + 'AnnouncementsDisplayName'
				forum_key = self._get_forum_key(forum_types, name, display_key)

				discussions = context.Discussions
				found_forum = discussions.get( forum_key )
				if found_forum is not None:
					announcements[ scope_name ] = found_forum

		if announcements:
			result[ 'AnnouncementForums' ] = items

@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseCatalogEntry)
class _LegacyCCEFieldDecorator(object):

	__metaclass__ = SingletonDecorator

	def _course_package(self, context):
		package = None
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

		if 	not result.get('LegacyPurchasableIcon') or \
			not result.get('LegacyPurchasableThumbnail'):

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

@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseInstanceScopedForum, interface.Interface)
class _SharedScopesForumDecorator(AbstractAuthenticatedRequestAwareDecorator):
	"""
	Puts the type of forum into the discussion.
	"""

	def _do_decorate_external(self, context, result):
		# Allow for native externaliazation, and copy to AutoTags;
		# this will assist with class evolutaion...AutoTags is visible
		# before people update their models
		scope_name = result.get('SharingScopeName')
		if not scope_name:
			scope_name = getattr(context, 'SharingScopeName', None)
		if not scope_name:
			# ok, is it on the tagged value?
			scope_name = interface.providedBy(context).get('SharingScopeName').queryTaggedValue('value')

		if scope_name:
			result.setdefault('AutoTags', []).append('SharingScopeName=' + scope_name)
			result['SharingScopeName'] = scope_name

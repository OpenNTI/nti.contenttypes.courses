#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Code to synchronize course-catalog folders with the disk. This also
defines the on-disk layout.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component
from zope import lifecycleevent
from zope.event import notify

from nti.contentlibrary.interfaces import IDelimitedHierarchyBucket
from nti.contentlibrary.interfaces import IDelimitedHierarchyKey

from nti.contentlibrary.bundle import BUNDLE_META_NAME
from nti.contentlibrary.bundle import sync_bundle_from_json_key
from nti.contentlibrary.bundle import PersistentContentPackageBundle

from nti.contentlibrary.dublincore import read_dublincore_from_named_key

from nti.dataserver.users.interfaces import IAvatarURL
from nti.dataserver.users.interfaces import IFriendlyNamed
from nti.dataserver.interfaces import ISharingTargetEntityIterable

from .interfaces import ES_CREDIT
from .interfaces import ENROLLMENT_SCOPE_VOCABULARY

from .interfaces import ICourseInstance
from .interfaces import ICourseCatalogEntry
from .interfaces import ICourseSubInstances
from .interfaces import IDenyOpenEnrollment
from .interfaces import INonPublicCourseInstance
from .interfaces import IContentCourseSubInstance
from .interfaces import ICourseInstanceVendorInfo
from .interfaces import CourseInstanceAvailableEvent
from .interfaces import IEnrollmentMappedCourseInstance

from .courses import ContentCourseInstance
from .courses import ContentCourseSubInstance
from .courses import CourseAdministrativeLevel

from .enrollment import check_enrollment_mapped
from .enrollment import check_deny_open_enrollment

from .legacy_catalog import _ntiid_from_entry

from ._role_parser import fill_roles_from_key
from ._role_parser import reset_roles_missing_key
from ._outline_parser import fill_outline_from_key
from ._assignment_override_parser import fill_asg_from_key
from ._catalog_entry_parser import fill_entry_from_legacy_key
from ._assignment_override_parser import reset_asg_missing_key

SECTION_FOLDER_NAME = 'Sections'
ROLE_INFO_NAME = 'role_info.json'
VENDOR_INFO_NAME = 'vendor_info.json'
CATALOG_INFO_NAME = 'course_info.json'
COURSE_OUTLINE_NAME = 'course_outline.xml'
INSTRUCTOR_INFO_NAME = 'instructor_info.json'
ASSIGNMENT_DATES_NAME = 'assignment_policies.json'

class IObjectEntrySynchronizer(interface.Interface):
	"""
	Something to synchronize one object and possibly its children.
	"""

	def synchronize(obj, bucket):
		"""
		Synchronize the object from the bucket.
		"""

@interface.implementer(IObjectEntrySynchronizer)
class _GenericFolderSynchronizer(object):

	_COURSE_KEY_NAME = BUNDLE_META_NAME
	_COURSE_INSTANCE_FACTORY = ContentCourseInstance
	_ADMIN_LEVEL_FACTORY = CourseAdministrativeLevel

	def __init__(self, folder, bucket):
		pass
	
	def _get_factory_for(self, bucket):
		# order matters.

		# Is this supposed to be a course instance?
		# course instances are minimally defined by the presence of their
		# bundle descriptor
		if bucket.getChildNamed(self._COURSE_KEY_NAME):
			return self._COURSE_INSTANCE_FACTORY

		# Otherwise, just a plain folder
		return self._ADMIN_LEVEL_FACTORY

	def synchronize(self, folder, bucket):
		# Find the things in the filesystem
		child_buckets = dict()
		for item in bucket.enumerateChildren():
			if IDelimitedHierarchyBucket.providedBy(item):
				child_buckets[item.__name__] = item

		# Remove anything the folder has that aren't on the
		# filesystem
		for folder_child_name in list(folder):
			if folder_child_name not in child_buckets:
				logger.info("Removing child %s (%r)",
							folder_child_name, folder[folder_child_name])
				del folder[folder_child_name]

		# Create anything the folder is missing if we
		# have a factory for it
		for bucket_child_name in child_buckets:
			__traceback_info__ = folder, bucket, bucket_child_name
			if bucket_child_name not in folder:
				# NOTE: We don't handle the case of a bucket
				# changing the type it should be
				child_bucket = child_buckets[bucket_child_name]
				factory = self._get_factory_for(child_bucket)
				if not factory:
					continue
				new_child_object = factory()
				new_child_object.root = child_bucket
				# Fire the added event
				__traceback_info__ = folder, child_bucket, new_child_object
				folder[bucket_child_name] = new_child_object

		# Synchronize everything
		for child_name, child in folder.items():
			child_bucket = child_buckets[child_name]
			sync = component.getMultiAdapter( (child, child_bucket),
											  IObjectEntrySynchronizer)
			sync.synchronize(child, child_bucket)

@interface.implementer(IObjectEntrySynchronizer)
@component.adapter(ICourseInstance, IDelimitedHierarchyBucket)
class _ContentCourseSynchronizer(object):

	def __init__(self, course, bucket):
		pass

	def synchronize(self, course, bucket):
		# TODO: Need to be setting NTIIDs based on the
		# bucket path for these guys
		__traceback_info__ = course, bucket

		# First, synchronize the bundle
		bundle_json_key = bucket.getChildNamed(BUNDLE_META_NAME)
		if not IDelimitedHierarchyKey.providedBy(bundle_json_key): # pragma: no cover
			raise ValueError("No bundle defined for course", course, bucket)

		bundle = None
		created_bundle = False
		if course.ContentPackageBundle is None:
			bundle = PersistentContentPackageBundle()
			bundle.root = bucket
			bundle.__parent__ = course
			course.ContentPackageBundle = bundle
			bundle.createdTime = bundle.lastModified = 0
			bundle.ntiid = _ntiid_from_entry(bundle, 'Bundle:CourseBundle')
			lifecycleevent.created(bundle)
			created_bundle = True

		# The catalog entry gets the default DublinCore metadata file name,
		# in this bucket, since it really describes the data.
		# The content bundle, on the other hand, gets a custom file
		sync_bundle_from_json_key(bundle_json_key, course.ContentPackageBundle,
								  dc_meta_name='bundle_dc_metadata.xml',
								  excluded_keys=('ntiid',))
		if created_bundle:
			lifecycleevent.added(bundle)

		self.update_common_info(course, bucket, try_legacy_content_bundle=True)

		notify(CourseInstanceAvailableEvent(course))

		sections_bucket = bucket.getChildNamed(SECTION_FOLDER_NAME)
		sync = component.getMultiAdapter( (course.SubInstances, sections_bucket) )
		sync.synchronize( course.SubInstances, sections_bucket )

		# After we've loaded all the sections, check to see if we should map enrollment
		if check_enrollment_mapped(course):
			interface.alsoProvides(course, IEnrollmentMappedCourseInstance)
		else:
			interface.noLongerProvides(course, IEnrollmentMappedCourseInstance)

		# check of open enrollment. Marke the entry as well
		entry = ICourseCatalogEntry(course)
		if check_deny_open_enrollment(course):
			interface.alsoProvides(entry, IDenyOpenEnrollment)
			interface.alsoProvides(course, IDenyOpenEnrollment)
		elif IDenyOpenEnrollment.providedBy(course):
			interface.noLongerProvides(entry, IDenyOpenEnrollment)
			interface.noLongerProvides(course, IDenyOpenEnrollment)
		
	@classmethod
	def update_common_info(cls, course, bucket, try_legacy_content_bundle=False):
		course.SharingScopes.initScopes()
		if ES_CREDIT in course.SharingScopes:
			# Make sure the credit scope, which is usually the smaller
			# scope, is set to expand and send notices.
			# TODO: We could do better with this by having the vocabulary
			# terms know what scopes should be like this and/or have a file
			# TODO: Because the scopes are now communities and have shoring storage
			# of their own, we don't really need to broadcast this out to each individual
			# stream storage, we just want an on-the-socket notification.
			try:
				ISharingTargetEntityIterable(course.SharingScopes[ES_CREDIT])
			except TypeError:
				interface.alsoProvides(course.SharingScopes[ES_CREDIT], ISharingTargetEntityIterable)
		cls.update_vendor_info(course, bucket)
		cls.update_outline(course, bucket, try_legacy_content_bundle=try_legacy_content_bundle)
		cls.update_catalog_entry(course, bucket, try_legacy_content_bundle=try_legacy_content_bundle)
		cls.update_instructor_roles(course, bucket)
		cls.update_assignment_dates(course, bucket)
		getattr(course, 'Discussions')

		cls.update_sharing_scopes_friendly_names(course)

	@classmethod
	def update_sharing_scopes_friendly_names(cls, course):
		cce = ICourseCatalogEntry(course)
		sharing_scopes_data = (ICourseInstanceVendorInfo(course)
							   .get('NTI', {})
							   .get("SharingScopesDisplayInfo", {}))

		for scope in course.SharingScopes.values():
			sharing_scope_data = sharing_scopes_data.get(scope.__name__, {})

			friendly_scope = IFriendlyNamed(scope)
			friendly_title = ENROLLMENT_SCOPE_VOCABULARY.getTerm(scope.__name__).title

			if sharing_scope_data.get('alias'):
				alias = sharing_scope_data['alias']
			elif cce.ProviderUniqueID:
				alias = cce.ProviderUniqueID + ' - ' + friendly_title
			else:
				alias = friendly_scope.alias

			if sharing_scope_data.get('realname'):
				realname = sharing_scope_data['realname']
			elif cce.title:
				realname = cce.title + ' - ' + friendly_title
			else:
				realname = friendly_scope.realname

			modified_scope = False
			if (realname, alias) != (friendly_scope.realname, friendly_scope.alias):
				friendly_scope.realname = realname
				friendly_scope.alias = alias
				lifecycleevent.modified(friendly_scope)
				modified_scope = True

			if (sharing_scope_data.get('avatarURL')
				and sharing_scope_data.get('avatarURL') != getattr(scope, 'avatarURL', '')):
				interface.alsoProvides(scope, IAvatarURL)
				scope.avatarURL = sharing_scope_data.get('avatarURL')
				modified_scope = True
			else:
				try:
					del scope.avatarURL
				except AttributeError:
					pass
				else:
					modified_scope = True
				interface.noLongerProvides(scope, IAvatarURL)

			if modified_scope:
				lifecycleevent.modified(scope)

	@classmethod
	def update_vendor_info(cls, course, bucket):
		vendor_json_key = bucket.getChildNamed(VENDOR_INFO_NAME)
		vendor_info = ICourseInstanceVendorInfo(course)
		if not vendor_json_key:
			vendor_info.clear()
			vendor_info.lastModified = 0
			vendor_info.createdTime = 0
		elif vendor_json_key.lastModified > vendor_info.lastModified:
			vendor_info.clear()
			vendor_info.update(vendor_json_key.readContentsAsJson())
			vendor_info.lastModified = vendor_json_key.lastModified
			vendor_info.createdTime = vendor_json_key.createdTime

	@classmethod
	def update_outline(cls, course, bucket, try_legacy_content_bundle=False):
		outline_xml_key = bucket.getChildNamed(COURSE_OUTLINE_NAME)
		outline_xml_node = None
		if not outline_xml_key and try_legacy_content_bundle:
			# Only want to do this for root courses
			if course.ContentPackageBundle:
				# Just take the first one. That should be all there
				# is in legacy cases
				for package in course.ContentPackageBundle.ContentPackages:
					outline_xml_key = package.index
					outline_xml_node = 'course'
					break

		# We actually want to delete anything it has
		# in case it's a subinstance so the parent can come through
		# again
		if not outline_xml_key:
			try:
				del course.Outline
			except AttributeError:
				pass
		else:
			try:
				course.prepare_own_outline()
			except AttributeError:
				pass
			fill_outline_from_key(course.Outline, outline_xml_key, xml_parent_name=outline_xml_node)

	@classmethod
	def update_catalog_entry(cls, course, bucket, try_legacy_content_bundle=False):
		catalog_json_key = bucket.getChildNamed(CATALOG_INFO_NAME)
		if not catalog_json_key and try_legacy_content_bundle:
			# Only want to do this for root courses
			if course.ContentPackageBundle:
				for package in course.ContentPackageBundle.ContentPackages:
					if package.does_sibling_entry_exist(CATALOG_INFO_NAME):
						catalog_json_key = package.make_sibling_key(CATALOG_INFO_NAME)
						break

		# TODO: Cleaning up?
		# XXX base_url
		catalog_entry = ICourseCatalogEntry(course)
		if catalog_json_key:
			fill_entry_from_legacy_key(catalog_entry, catalog_json_key)
			# The catalog entry gets the default dublincore info
			# file; for the bundle, we use a different name
			read_dublincore_from_named_key(catalog_entry, bucket)

		if not getattr(catalog_entry, 'root', None):
			catalog_entry.root = bucket

		if INonPublicCourseInstance.providedBy(catalog_entry):
			interface.alsoProvides(course, INonPublicCourseInstance)
		elif INonPublicCourseInstance.providedBy(course):
			interface.noLongerProvides(course, INonPublicCourseInstance)

	@classmethod
	def update_instructor_roles(cls, course, bucket):
		role_json_key = bucket.getChildNamed(ROLE_INFO_NAME)
		if role_json_key:
			fill_roles_from_key(course, role_json_key)
		else:
			reset_roles_missing_key(course)

	@classmethod
	def update_assignment_dates(cls, subcourse, bucket):
		key = bucket.getChildNamed(ASSIGNMENT_DATES_NAME)
		if key is not None:
			fill_asg_from_key(subcourse, key)
		else:
			reset_asg_missing_key(subcourse)

@component.adapter(ICourseSubInstances, IDelimitedHierarchyBucket)
class _CourseSubInstancesSynchronizer(_GenericFolderSynchronizer):

	#: We create sub-instances...
	_COURSE_INSTANCE_FACTORY = ContentCourseSubInstance
	
	#: and we do not recurse into folders
	_ADMIN_LEVEL_FACTORY = None

	_COURSE_KEY_NAME = None

	def _get_factory_for(self, bucket):
		# We only support one level, and they must all
		# be courses if they have one of the known
		# files in it
		for possible_key in (ROLE_INFO_NAME, COURSE_OUTLINE_NAME,
							 VENDOR_INFO_NAME, ASSIGNMENT_DATES_NAME,
							 CATALOG_INFO_NAME):
			if bucket.getChildNamed(possible_key):
				return self._COURSE_INSTANCE_FACTORY

@interface.implementer(IObjectEntrySynchronizer)
@component.adapter(ICourseSubInstances, interface.Interface)
class _MissingCourseSubInstancesSynchronizer(object):

	def __init__(self, instances, bucket):
		pass

	def synchronize(self, instances, _):
		instances.clear()

@interface.implementer(IObjectEntrySynchronizer)
@component.adapter(IContentCourseSubInstance, IDelimitedHierarchyBucket)
class _ContentCourseSubInstanceSynchronizer(object):

	def __init__(self, subcourse, bucket):
		pass

	def synchronize(self, subcourse, bucket):
		__traceback_info__ = subcourse, bucket
		_ContentCourseSynchronizer.update_common_info(subcourse, bucket)

		notify(CourseInstanceAvailableEvent(subcourse))

def synchronize_catalog_from_root(catalog_folder, root):
	"""
	Given a :class:`CourseCatalogFolder` and a class:`.IDelimitedHierarchyBucket`,
	synchronize the course catalog to match.
	"""

	component.getMultiAdapter( (catalog_folder, root),
							   IObjectEntrySynchronizer).synchronize(catalog_folder, root)

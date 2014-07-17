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

from nti.contentlibrary.interfaces import IDelimitedHierarchyBucket
from nti.contentlibrary.interfaces import IDelimitedHierarchyKey

class IObjectEntrySynchronizer(interface.Interface):
	"""
	Something to synchronize one object and possibly its children.
	"""

	def synchronize(object, bucket):
		"""
		Synchronize the object from the bucket.
		"""

from zope.event import notify

from .interfaces import ICourseInstance
from .interfaces import ICourseInstanceVendorInfo
from .interfaces import ICourseSubInstances
from .interfaces import IContentCourseSubInstance
from .interfaces import ICourseCatalogEntry
from .interfaces import CourseInstanceAvailableEvent

from .courses import ContentCourseInstance
from .courses import ContentCourseSubInstance
from .courses import CourseAdministrativeLevel

from ._outline_parser import fill_outline_from_key
from ._catalog_entry_parser import fill_entry_from_legacy_key
from ._role_parser import fill_roles_from_key
from ._role_parser import reset_roles_missing_key

from nti.contentlibrary.bundle import PersistentContentPackageBundle
from nti.contentlibrary.bundle import sync_bundle_from_json_key
from nti.contentlibrary.bundle import BUNDLE_META_NAME

VENDOR_INFO_NAME = 'vendor_info.json'
COURSE_OUTLINE_NAME = 'course_outline.xml'
INSTRUCTOR_INFO_NAME = 'instructor_info.json'
CATALOG_INFO_NAME = 'course_info.json'
ROLE_INFO_NAME = 'role_info.json'
SECTION_FOLDER_NAME = 'Sections'

@interface.implementer(IObjectEntrySynchronizer)
class _GenericFolderSynchronizer(object):

	def __init__(self, folder, bucket):
		pass

	_COURSE_INSTANCE_FACTORY = ContentCourseInstance
	_COURSE_KEY_NAME = BUNDLE_META_NAME
	_ADMIN_LEVEL_FACTORY = CourseAdministrativeLevel

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
				del folder[folder_child_name]

		# Create anything the folder is missing if we
		# have a factory for it
		for bucket_child_name in child_buckets:
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

		# First, synchronize the bundle
		bundle_json_key = bucket.getChildNamed(BUNDLE_META_NAME)
		if not IDelimitedHierarchyKey.providedBy(bundle_json_key): # pragma: no cover
			raise ValueError("No bundle defined for course", course, bucket)

		bundle_modified = 0
		if course.ContentPackageBundle is None:
			bundle = PersistentContentPackageBundle()
			bundle.root = bucket
			course.ContentPackageBundle = bundle
			bundle.lastModified = 0
			bundle.createdTime = 0

		sync_bundle_from_json_key(bundle_json_key, course.ContentPackageBundle)
		bundle_modified = course.ContentPackageBundle.lastModified

		self.update_vendor_info(course, bucket)
		self.update_outline(course, bucket, try_legacy_content_bundle=True)
		self.update_catalog_entry(course, bucket, try_legacy_content_bundle=True)
		self.update_instructor_roles(course, bucket)
		course.SharingScopes.initScopes()
		getattr(course, 'Discussions')

		notify(CourseInstanceAvailableEvent(course))

		sections_bucket = bucket.getChildNamed(SECTION_FOLDER_NAME)
		sync = component.getMultiAdapter( (course.SubInstances, sections_bucket) )
		sync.synchronize( course.SubInstances, sections_bucket )


	@classmethod
	def update_vendor_info(cls, course, bucket):
		vendor_json_key = bucket.getChildNamed(VENDOR_INFO_NAME)
		vendor_info = ICourseInstanceVendorInfo(course)
		if not vendor_json_key:
			vendor_info.clear()
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
		if catalog_json_key:
			catalog_entry = ICourseCatalogEntry(course)
			fill_entry_from_legacy_key(catalog_entry, catalog_json_key)

	@classmethod
	def update_instructor_roles(cls, course, bucket):
		role_json_key = bucket.getChildNamed(ROLE_INFO_NAME)
		if role_json_key:
			fill_roles_from_key(course, role_json_key)
		else:
			reset_roles_missing_key(course)

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
		for possible_key in (ROLE_INFO_NAME, COURSE_OUTLINE_NAME, VENDOR_INFO_NAME):
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
		subcourse.SharingScopes.initScopes()
		_ContentCourseSynchronizer.update_vendor_info(subcourse, bucket)
		_ContentCourseSynchronizer.update_outline(subcourse, bucket)
		_ContentCourseSynchronizer.update_catalog_entry(subcourse, bucket)
		_ContentCourseSynchronizer.update_instructor_roles(subcourse, bucket)
		subcourse.SharingScopes.initScopes()
		getattr(subcourse, 'Discussions')
		notify(CourseInstanceAvailableEvent(subcourse))

def synchronize_catalog_from_root(catalog_folder, root):
	"""
	Given a :class:`CourseCatalogFolder` and a class:`.IDelimitedHierarchyBucket`,
	synchronize the course catalog to match.
	"""

	component.getMultiAdapter( (catalog_folder, root),
							   IObjectEntrySynchronizer).synchronize(catalog_folder, root)

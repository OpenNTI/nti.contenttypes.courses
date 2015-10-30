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

import time

from zope import interface
from zope import component
from zope import lifecycleevent

from zope.container.contained import Contained

from zope.event import notify

from zope.site.interfaces import ILocalSiteManager

from nti.common.string import safestr
from nti.common.representation import WithRepr

from nti.contentlibrary import ContentRemovalException

from nti.contentlibrary.bundle import BUNDLE_META_NAME
from nti.contentlibrary.bundle import sync_bundle_from_json_key
from nti.contentlibrary.bundle import PersistentContentPackageBundle

from nti.contentlibrary.interfaces import ISynchronizationParams
from nti.contentlibrary.interfaces import IDelimitedHierarchyKey
from nti.contentlibrary.interfaces import IDelimitedHierarchyBucket

from nti.contentlibrary.dublincore import read_dublincore_from_named_key

from nti.dataserver.users.interfaces import IAvatarURL
from nti.dataserver.users.interfaces import IBackgroundURL
from nti.dataserver.users.interfaces import IFriendlyNamed
from nti.dataserver.interfaces import ISharingTargetEntityIterable

from nti.schema.schema import EqHash
from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from .courses import ContentCourseInstance
from .courses import ContentCourseSubInstance
from .courses import CourseAdministrativeLevel

from .enrollment import check_enrollment_mapped
from .enrollment import has_deny_open_enrollment
from .enrollment import check_deny_open_enrollment

from .interfaces import ES_CREDIT
from .interfaces import ENROLLMENT_SCOPE_VOCABULARY

from .interfaces import ICourseInstance
from .interfaces import ICourseCatalogEntry
from .interfaces import ICourseSubInstances
from .interfaces import IDenyOpenEnrollment
from .interfaces import CourseRolesSynchronized
from .interfaces import CatalogEntrySynchronized
from .interfaces import INonPublicCourseInstance
from .interfaces import IContentCourseSubInstance
from .interfaces import ICourseInstanceVendorInfo
from .interfaces import CourseInstanceAvailableEvent
from .interfaces import IEnrollmentMappedCourseInstance

from .legacy_catalog import _ntiid_from_entry

from ._role_parser import fill_roles_from_key
from ._role_parser import reset_roles_missing_key

from ._outline_parser import fill_outline_from_key

from ._assessment_override_parser import fill_asg_from_key

from ._catalog_entry_parser import fill_entry_from_legacy_key

from ._assessment_override_parser import reset_asg_missing_key
from ._assessment_policy_validator import validate_assigment_policies

from .grading import reset_grading_policy
from .grading import fill_grading_policy_from_key

from .discussions import parse_discussions

from .interfaces import IObjectEntrySynchronizer
from .interfaces import ICourseSynchronizationResults
from .interfaces import SECTIONS as SECTION_FOLDER_NAME
from .interfaces import DISCUSSIONS as DISCUSSION_FOLDER_NAME

ROLE_INFO_NAME = 'role_info.json'
VENDOR_INFO_NAME = 'vendor_info.json'
CATALOG_INFO_NAME = 'course_info.json'
COURSE_OUTLINE_NAME = 'course_outline.xml'
GRADING_POLICY_NAME = 'grading_policy.json'
INSTRUCTOR_INFO_NAME = 'instructor_info.json'
ASSIGNMENT_DATES_NAME = 'assignment_policies.json'

def _site_name(registry=None):
	registry = component.getSiteManager() if registry is None else registry
	if ILocalSiteManager.providedBy(registry):
		result = registry.__parent__.__name__
	else:
		result = getattr(registry, '__name__', None)
	return safestr(result)

@WithRepr
@EqHash('NTIID')
@interface.implementer(ICourseSynchronizationResults)
class CourseSynchronizationResults(SchemaConfigured, Contained):
	createDirectFieldProperties(ICourseSynchronizationResults)

def _get_sync_packages(**kwargs):
	params = kwargs.get('params')  # sync params
	packages = params.packages if params is not None else ()
	packages = packages if isinstance(packages, set) else set(packages)
	return packages

def _get_sync_results(context, sync_results=None, **kwargs):
	if sync_results is None:
		entry = ICourseCatalogEntry(context)
		results = kwargs.get('results') or []
		sync_results = CourseSynchronizationResults(NTIID=entry.ntiid, Site=_site_name())
		results.append(sync_results)
	return sync_results

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
		# course instances are minimally defined by the presence of
		# their bundle descriptor
		if bucket.getChildNamed(self._COURSE_KEY_NAME):
			return self._COURSE_INSTANCE_FACTORY

		# Otherwise, just a plain folder
		return self._ADMIN_LEVEL_FACTORY

	def synchronize(self, folder, bucket, **kwargs):
		params = kwargs.get('params')
		if params and ISynchronizationParams.providedBy(params):
			allowRemoval = params.allowRemoval
		else:
			allowRemoval = True

		# Find the things in the filesystem
		child_buckets = dict()
		for item in bucket.enumerateChildren():
			if IDelimitedHierarchyBucket.providedBy(item):
				child_buckets[item.__name__] = item

		# Remove anything the folder has that aren't on the
		# filesystem
		for folder_child_name in list(folder):
			if folder_child_name not in child_buckets:
				child_folder = folder[folder_child_name]
				if 	not allowRemoval and self._COURSE_INSTANCE_FACTORY is not None and \
					isinstance(child_folder, self._COURSE_INSTANCE_FACTORY):
					raise ContentRemovalException(
							"Cannot remove course without explicitly allowing it")
				else:
					logger.info("Removing child %s (%r)", folder_child_name, child_folder)
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
			sync = component.getMultiAdapter((child, child_bucket),
											  IObjectEntrySynchronizer)
			sync.synchronize(child, child_bucket, **kwargs)

@interface.implementer(IObjectEntrySynchronizer)
@component.adapter(ICourseInstance, IDelimitedHierarchyBucket)
class _ContentCourseSynchronizer(object):

	def __init__(self, course, bucket):
		pass

	def synchronize(self, course, bucket, **kwargs):
		__traceback_info__ = course, bucket
		entry = ICourseCatalogEntry(course)

		# gather/prepare sync params/results
		packages = _get_sync_packages(**kwargs)
		sync_results = _get_sync_results(entry, **kwargs)

		# First, synchronize the bundle
		bundle_json_key = bucket.getChildNamed(BUNDLE_META_NAME)
		if not IDelimitedHierarchyKey.providedBy(bundle_json_key):  # pragma: no cover
			raise ValueError("No bundle defined for course", course, bucket)

		bundle = None
		created_bundle = False
		if course.ContentPackageBundle is None:
			# mark results
			created_bundle = True
			sync_results.ContentBundleCreated = True
			# create bundle
			bundle = PersistentContentPackageBundle()
			bundle.root = bucket
			bundle.__parent__ = course
			bundle.createdTime = bundle.lastModified = 0
			bundle.ntiid = _ntiid_from_entry(bundle, 'Bundle:CourseBundle')
			# register w/ course and notify
			course.ContentPackageBundle = bundle
			lifecycleevent.created(bundle)
		elif packages:  # check if underlying library was updated
			ntiids = {x.ntiid for x in course.ContentPackageBundle.ContentPackages}
			# if none of the bundle pacakges were updated return
			if not ntiids.intersection(packages):
				return

		# The catalog entry gets the default DublinCore metadata file name,
		# in this bucket, since it really describes the data.
		# The content bundle, on the other hand, gets a custom file
		modified = sync_bundle_from_json_key(bundle_json_key, course.ContentPackageBundle,
								  			 dc_meta_name='bundle_dc_metadata.xml',
								  			 excluded_keys=('ntiid',))
		if modified:
			sync_results.ContentBundleUpdated = True

		if created_bundle:
			lifecycleevent.added(bundle)

		self.update_common_info(course, bucket,
								sync_results=sync_results,
								try_legacy_content_bundle=True)

		self.update_deny_open_enrollment(course)

		notify(CourseInstanceAvailableEvent(course, bucket))

		sections_bucket = bucket.getChildNamed(SECTION_FOLDER_NAME)
		sync = component.getMultiAdapter((course.SubInstances, sections_bucket))
		sync.synchronize(course.SubInstances, sections_bucket, **kwargs)

		# After we've loaded all the sections, check to see if we should map enrollment
		if check_enrollment_mapped(course):
			interface.alsoProvides(course, IEnrollmentMappedCourseInstance)
		else:
			interface.noLongerProvides(course, IEnrollmentMappedCourseInstance)

		# mark last sync time
		course.lastSynchronized = entry.lastSynchronized = time.time()

	@classmethod
	def update_common_info(cls, course, bucket,
						   sync_results=None,
						   try_legacy_content_bundle=False):
		sync_results = _get_sync_results(course, sync_results)

		course.SharingScopes.initScopes()
		if ES_CREDIT in course.SharingScopes:
			# Make sure the credit scope, which is usually the smaller
			# scope, is set to expand and send notices.
			#
			# TODO: We could do better with this by having the vocabulary
			# terms know what scopes should be like this and/or have a file
			#
			# TODO: Because the scopes are now communities and have shoring storage
			# of their own, we don't really need to broadcast this out to each individual
			# stream storage, we just want an on-the-socket notification.
			try:
				ISharingTargetEntityIterable(course.SharingScopes[ES_CREDIT])
			except TypeError:
				interface.alsoProvides(course.SharingScopes[ES_CREDIT],
									   ISharingTargetEntityIterable)

		cls.update_vendor_info(course, bucket, sync_results)
		cls.update_outline(course=course,
						   bucket=bucket,
						   sync_results=sync_results,
						   try_legacy_content_bundle=try_legacy_content_bundle)

		cls.update_catalog_entry(course=course,
								 bucket=bucket,
								 sync_results=sync_results,
								 try_legacy_content_bundle=try_legacy_content_bundle)

		cls.update_instructor_roles(course, bucket, sync_results=sync_results)
		cls.update_assignment_policies(course, bucket, sync_results=sync_results)

		# make sure Discussions are initialized
		getattr(course, 'Discussions')
		cls.update_sharing_scopes_friendly_names(course, sync_results=sync_results)

		# validate assigment policies
		cls.validate_assigment_policies(course, bucket)

		# check grading policy. it must be done after validating assigments
		cls.update_grading_policy(course, bucket, sync_results=sync_results)

		# update dicussions
		cls.update_course_discussions(course, bucket)

	@classmethod
	def update_sharing_scopes_friendly_names(cls, course, sync_results=None):
		sync_results = _get_sync_results(course, sync_results)
		cce = ICourseCatalogEntry(course)
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

			def _imageURL(scope, image_iface, image_attr):
				result = False
				scope_imageURL = getattr(scope, image_attr, None)
				inputed_imageURL = sharing_scope_data.get(image_attr, None)
				if inputed_imageURL:
					if scope_imageURL != inputed_imageURL:
						logger.info("Adjusting scope %s %s to %s for course %s",
									scope_name, image_attr, inputed_imageURL, cce.ntiid)
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
									 scope_name, image_attr, cce.ntiid)
				return result

			modified_scope = _imageURL(scope, IAvatarURL, 'avatarURL') or modified_scope
			modified_scope = _imageURL(scope, IBackgroundURL, 'backgroundURL') or modified_scope

			if modified_scope:
				lifecycleevent.modified(scope)
				sync_results.SharingScopesUpdated = True

	@classmethod
	def update_vendor_info(cls, course, bucket, sync_results=None):
		sync_results = _get_sync_results(course, sync_results)
		vendor_json_key = bucket.getChildNamed(VENDOR_INFO_NAME)
		vendor_info = ICourseInstanceVendorInfo(course)
		if not vendor_json_key:
			vendor_info.clear()
			vendor_info.createdTime = 0
			vendor_info.lastModified = 0
			sync_results.VendorInfoReseted = True
		elif vendor_json_key.lastModified > vendor_info.lastModified:
			vendor_info.clear()
			vendor_info.update(vendor_json_key.readContentsAsJson())
			vendor_info.createdTime = vendor_json_key.createdTime
			vendor_info.lastModified = vendor_json_key.lastModified
			sync_results.VendorInfoUpdated = True

	@classmethod
	def update_outline(cls, course, bucket, sync_results=None,
					   try_legacy_content_bundle=False,
					   force=False):
		sync_results = _get_sync_results(course, sync_results)

		outline_xml_node = None
		outline_xml_key = bucket.getChildNamed(COURSE_OUTLINE_NAME)
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
		# in case it's a subinstance so the parent can come through again
		if not outline_xml_key:
			try:
				if course._delete_Outline():
					sync_results.OutlineDeleted = True
			except AttributeError:
				try:
					del course.Outline
					sync_results.OutlineDeleted = True
				except AttributeError:
					pass
		else:
			try:
				course.prepare_own_outline()
			except AttributeError:
				pass
			if fill_outline_from_key(course.Outline,
								  	 outline_xml_key,
								  	 xml_parent_name=outline_xml_node,
								  	 force=force):
				sync_results.OutlineUpdated = True

	@classmethod
	def update_catalog_entry(cls, course, bucket, sync_results=None,
							 try_legacy_content_bundle=False):
		sync_results = _get_sync_results(course, sync_results)
		catalog_json_key = bucket.getChildNamed(CATALOG_INFO_NAME)
		if not catalog_json_key and try_legacy_content_bundle:
			# Only want to do this for root courses
			if course.ContentPackageBundle:
				for package in course.ContentPackageBundle.ContentPackages:
					if package.does_sibling_entry_exist(CATALOG_INFO_NAME):
						catalog_json_key = package.make_sibling_key(CATALOG_INFO_NAME)
						break

		modified = False
		catalog_entry = ICourseCatalogEntry(course)
		if catalog_json_key:
			modified = fill_entry_from_legacy_key(catalog_entry, catalog_json_key)
			# The catalog entry gets the default dublincore info
			# file; for the bundle, we use a different name
			modified = (read_dublincore_from_named_key(catalog_entry, bucket) != None) or modified

		if not getattr(catalog_entry, 'root', None):
			catalog_entry.root = bucket
			modified = True

		if INonPublicCourseInstance.providedBy(catalog_entry):
			interface.alsoProvides(course, INonPublicCourseInstance)
		elif INonPublicCourseInstance.providedBy(course):
			interface.noLongerProvides(course, INonPublicCourseInstance)

		if modified:
			notify(CatalogEntrySynchronized(catalog_entry))
			sync_results.CatalogEntryUpdated = True

	@classmethod
	def update_instructor_roles(cls, course, bucket, sync_results=None):
		sync_results = _get_sync_results(course, sync_results)
		role_json_key = bucket.getChildNamed(ROLE_INFO_NAME)
		if role_json_key:
			if fill_roles_from_key(course, role_json_key):
				notify(CourseRolesSynchronized(course))
				sync_results.InstructorRolesUpdated = True
		else:
			reset_roles_missing_key(course)
			notify(CourseRolesSynchronized(course))
			sync_results.InstructorRolesReseted = True

	@classmethod
	def update_assignment_policies(cls, course, bucket, sync_results=None):
		sync_results = _get_sync_results(course, sync_results)
		key = bucket.getChildNamed(ASSIGNMENT_DATES_NAME)
		if key is not None:
			if fill_asg_from_key(course, key):
				sync_results.AssignmentPoliciesUpdated = True
		elif reset_asg_missing_key(course):
			sync_results.AssignmentPoliciesReseted = True

	@classmethod
	def update_grading_policy(cls, course, bucket, sync_results=None):
		sync_results = _get_sync_results(course, sync_results)
		key = bucket.getChildNamed(GRADING_POLICY_NAME)
		if key is not None:
			if fill_grading_policy_from_key(course, key):
				sync_results.GradingPolicyUpdated = True
		elif reset_grading_policy(course):
			sync_results.GradingPolicyDeleted = True

	@classmethod
	def validate_assigment_policies(cls, course, bucket):
		validate_assigment_policies(course)

	@classmethod
	def set_deny_open_enrollment(self, course, deny):
		entry = ICourseCatalogEntry(course)
		if deny:
			if not IDenyOpenEnrollment.providedBy(course):
				interface.alsoProvides(entry, IDenyOpenEnrollment)
				interface.alsoProvides(course, IDenyOpenEnrollment)
		elif IDenyOpenEnrollment.providedBy(course):
			interface.noLongerProvides(entry, IDenyOpenEnrollment)
			interface.noLongerProvides(course, IDenyOpenEnrollment)

	@classmethod
	def update_deny_open_enrollment(cls, course):
		deny = check_deny_open_enrollment(course)
		cls.set_deny_open_enrollment(course, deny)

	@classmethod
	def update_course_discussions(cls, course, bucket, sync_results=None):
		sync_results = _get_sync_results(course, sync_results)
		key = bucket.getChildNamed(DISCUSSION_FOLDER_NAME)
		if key is not None and IDelimitedHierarchyBucket.providedBy(key):
			result = parse_discussions(course, key)
			sync_results.CourseDiscussionsUpdated = result

@component.adapter(ICourseSubInstances, IDelimitedHierarchyBucket)
class _CourseSubInstancesSynchronizer(_GenericFolderSynchronizer):

	# We create sub-instances...
	_COURSE_INSTANCE_FACTORY = ContentCourseSubInstance

	# and we do not recurse into folders
	_ADMIN_LEVEL_FACTORY = None

	_COURSE_KEY_NAME = None

	def _get_factory_for(self, bucket):
		# We only support one level, and they must all
		# be courses if they have one of the known files in it
		for possible_key in (ROLE_INFO_NAME, COURSE_OUTLINE_NAME,
							 VENDOR_INFO_NAME, ASSIGNMENT_DATES_NAME,
							 CATALOG_INFO_NAME, DISCUSSION_FOLDER_NAME):
			if bucket.getChildNamed(possible_key):
				return self._COURSE_INSTANCE_FACTORY

@interface.implementer(IObjectEntrySynchronizer)
@component.adapter(ICourseSubInstances, interface.Interface)
class _MissingCourseSubInstancesSynchronizer(object):

	def __init__(self, instances, bucket):
		pass

	def synchronize(self, instances, *args, **kwargs):
		instances.clear()

@interface.implementer(IObjectEntrySynchronizer)
@component.adapter(IContentCourseSubInstance, IDelimitedHierarchyBucket)
class _ContentCourseSubInstanceSynchronizer(object):

	def __init__(self, subcourse, bucket):
		pass

	def synchronize(self, subcourse, bucket, **kwargs):
		__traceback_info__ = subcourse, bucket

		sync_results = _get_sync_results(subcourse, **kwargs)
		_ContentCourseSynchronizer.update_common_info(subcourse, bucket,
													  sync_results=sync_results)

		# check for open enrollment
		if has_deny_open_enrollment(subcourse):
			_ContentCourseSynchronizer.update_deny_open_enrollment(subcourse)
		else:
			# inherit from parent
			deny = check_deny_open_enrollment(subcourse.__parent__.__parent__)
			_ContentCourseSynchronizer.set_deny_open_enrollment(subcourse, deny)

		# mark last sync time
		entry = ICourseCatalogEntry(subcourse)
		subcourse.lastSynchronized = entry.lastSynchronized = time.time()

		notify(CourseInstanceAvailableEvent(subcourse, bucket))

def synchronize_catalog_from_root(catalog_folder, root, **kwargs):
	"""
	Given a :class:`CourseCatalogFolder` and a class:`.IDelimitedHierarchyBucket`,
	synchronize the course catalog to match.
	"""
	synchronizer = component.getMultiAdapter((catalog_folder, root),
							   				 IObjectEntrySynchronizer)
	synchronizer.synchronize(catalog_folder, root, **kwargs)

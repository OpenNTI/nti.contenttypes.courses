#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import time
import shutil
import simplejson

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.event import notify

from ZODB.interfaces import IConnection

from nti.cabinet.filer import transfer_to_native_file

from nti.contentlibrary.bundle import BUNDLE_META_NAME
from nti.contentlibrary.bundle import sync_bundle_from_json_key

from nti.contentlibrary.dublincore import DCMETA_FILENAME

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.courses._assessment_override_parser import fill_asg_from_json

from nti.contenttypes.courses._bundle import created_content_package_bundle

from nti.contenttypes.courses._enrollment import update_deny_open_enrollment
from nti.contenttypes.courses._enrollment import check_enrollment_mapped_course

from nti.contenttypes.courses._catalog_entry_parser import update_entry_from_legacy_key

from nti.contenttypes.courses._role_parser import fill_roles_from_json

from nti.contenttypes.courses._sharing_scopes import update_sharing_scopes_friendly_names

from nti.contenttypes.courses import ROLE_INFO_NAME
from nti.contenttypes.courses import VENDOR_INFO_NAME
from nti.contenttypes.courses import CATALOG_INFO_NAME
from nti.contenttypes.courses import COURSE_OUTLINE_NAME
from nti.contenttypes.courses import ASSIGNMENT_POLICIES_NAME

from nti.contenttypes.courses.interfaces import SECTIONS, ICourseOutlineNode

from nti.contenttypes.courses.interfaces import iface_of_node

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.contenttypes.courses.interfaces import CourseRolesSynchronized
from nti.contenttypes.courses.interfaces import CourseVendorInfoSynchronized

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import clear_course_outline
from nti.contenttypes.courses.utils import get_course_vendor_info
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.internalization import update_from_external_object

from nti.site.hostpolicy import get_host_site

from nti.site.interfaces import IHostPolicyFolder

from nti.site.utils import registerUtility

from nti.traversal.traversal import find_interface

@interface.implementer(ICourseSectionImporter)
class BaseSectionImporter(object):

	def _prepare(self, data):
		if isinstance(data, bytes):
			data = unicode(data, 'utf-8')
		return data

	def load(self, source):
		if hasattr(source, "read"):
			data = self._prepare(source.read())
			result = simplejson.loads(data)
		elif hasattr(source, "readContents"):
			data = self._prepare(source.readContents())
			result = simplejson.loads(data)
		elif hasattr(source, "data"):
			data = self._prepare(source.data)
			result = simplejson.loads(data)
		else:
			result = simplejson.loads(self._prepare(source))
		return result

	def course_bucket_path(self, course):
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s/" % (SECTIONS, course.__name__)
		else:
			bucket = u''
		return bucket

	def safe_get(self, filer, href):
		path, _ = os.path.split(href)
		if path:
			if filer.is_bucket(path):
				result = filer.get(href)
			else:
				result = None
		else:
			result = filer.get(href)
		return result

@interface.implementer(ICourseSectionImporter)
class CourseOutlineImporter(BaseSectionImporter):

	def _update_and_register(self, course, ext_obj):
		# require connection
		connection = IConnection(course)
		def _object_hook(k, v, x):
			if ICourseOutlineNode.providedBy(v) and not ICourseOutline.providedBy(v):
				connection.add(v)
			return v
		update_from_external_object(course.Outline,
									ext_obj,
									notify=False,
									object_hook=_object_hook)

		# get site registry
		folder = find_interface(course, IHostPolicyFolder, strict=False)
		site = get_host_site(folder.__name__)
		registry = site.getSiteManager()

		# register nodes
		def _recur(node):
			if not ICourseOutline.providedBy(node):
				registerUtility(registry,
								node,
							  	name=node.ntiid,
							  	provided=iface_of_node(node))

			for child in node.values():
				_recur(child)
		_recur(course.Outline)

	def _delete_outline(self, course):
		clear_course_outline(course)
		if ICourseSubInstance.providedBy(course):
			course.prepare_own_outline()
		
	def process(self, context, filer):
		course = ICourseInstance(context)
		path = self.course_bucket_path(course) + COURSE_OUTLINE_NAME
		source = self.safe_get(filer, path)
		if source is not None:
			ext_obj = self.load(source)
			self._delete_outline(course) # not merging
			self._update_and_register(course, ext_obj)
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class VendorInfoImporter(BaseSectionImporter):

	def process(self, context, filer):
		course = ICourseInstance(context)
		path = self.course_bucket_path(course) + VENDOR_INFO_NAME
		source = self.safe_get(filer, path)
		if source is not None:
			# update vendor info
			verdor_info = get_course_vendor_info(course, True)
			verdor_info.clear()  # not merging
			verdor_info.update(self.load(source))
			verdor_info.lastModified = time.time()
			notify(CourseVendorInfoSynchronized(course))

			# update sharing scope names
			update_sharing_scopes_friendly_names(course)

			# update deny open enrollment
			update_deny_open_enrollment(course)

			# check mapped enrollment
			check_enrollment_mapped_course(course)

		# process subinstances
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class RoleInfoImporter(BaseSectionImporter):

	def process(self, context, filer):
		course = ICourseInstance(context)
		path = self.course_bucket_path(course) + ROLE_INFO_NAME
		source = self.safe_get(filer, path)
		if source is not None:
			source = self.load(source)
			fill_roles_from_json(course, source)
			notify(CourseRolesSynchronized(course))
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class AssignmentPoliciesImporter(BaseSectionImporter):

	def process(self, context, filer):
		course = ICourseInstance(context)
		path = self.course_bucket_path(course) + ASSIGNMENT_POLICIES_NAME
		source = self.safe_get(filer, path)
		if source is not None:
			source = self.load(source)
			fill_asg_from_json(course, source, time.time())
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class BundlePresentationAssetsImporter(BaseSectionImporter):

	__PA__ = 'presentation-assets'

	def _transfer(self, filer, filer_path, disk_path):
		if not os.path.exists(disk_path):
			os.makedirs(disk_path)
		for path in filer.list(filer_path):
			name = filer.key_name(path)
			new_path = os.path.join(disk_path, name)
			if filer.is_bucket(path):
				self._transfer(filer, path, new_path)
			else:
				source = filer.get(path)
				transfer_to_native_file(source, new_path)

	def process(self, context, filer):
		course = ICourseInstance(context)
		root = course.root  # must exists
		if root is None or not IFilesystemBucket.providedBy(root):
			return
		path = self.course_bucket_path(course) + self.__PA__
		if filer.is_bucket(path):
			root_path = os.path.join(root.absolute_path, self.__PA__)
			shutil.rmtree(root_path, True)  # not merging
			self._transfer(filer, path, root_path)
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class CourseInfoImporter(BaseSectionImporter):

	def process(self, context, filer):
		course = ICourseInstance(context)
		course.SharingScopes.initScopes()

		# make sure Discussions are initialized
		getattr(course, 'Discussions')

		root = course.root  # must exists
		if not IFilesystemBucket.providedBy(root):
			return
		path = self.course_bucket_path(course) + CATALOG_INFO_NAME
		source = self.safe_get(filer, path)
		if source is None:
			return
		new_path = os.path.join(root.absolute_path, CATALOG_INFO_NAME)
		transfer_to_native_file(source, new_path)
		key = root.getChildNamed(CATALOG_INFO_NAME)

		path = self.course_bucket_path(course) + DCMETA_FILENAME
		source = self.safe_get(filer, path)
		if source is not None:
			new_path = os.path.join(root.absolute_path, DCMETA_FILENAME)
			transfer_to_native_file(source, new_path)

		entry = ICourseCatalogEntry(course)
		update_entry_from_legacy_key(entry, key, root, force=True)

		# process subinstances
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class BundleMetaInfoImporter(BaseSectionImporter):

	def process(self, context, filer):
		course = ICourseInstance(context)
		course = get_parent_course(course)
		root = course.root
		if 		ICourseSubInstance.providedBy(course) \
			or	not IFilesystemBucket.providedBy(root):
			return
		source = self.safe_get(filer, BUNDLE_META_NAME)
		if source is None:
			return

		# save on disk
		new_path = os.path.join(root.absolute_path, BUNDLE_META_NAME)
		transfer_to_native_file(source, new_path)

		source = self.safe_get(filer, "bundle_dc_metadata.xml")
		if source is not None:
			new_path = os.path.join(root.absolute_path, "bundle_dc_metadata.xml")
			transfer_to_native_file(source, new_path)

		# create bundle if required
		created_bundle = created_content_package_bundle(course, root)
		if created_bundle:
			lifecycleevent.created(course.ContentPackageBundle)

		# sync
		bundle_json_key = root.getChildNamed(BUNDLE_META_NAME)
		sync_bundle_from_json_key(bundle_json_key,
								  course.ContentPackageBundle,
								  dc_meta_name='bundle_dc_metadata.xml',
								  excluded_keys=('ntiid',),
								  dc_bucket=root)

@interface.implementer(ICourseImporter)
class CourseImporter(object):

	def process(self, context, filer):
		course = ICourseInstance(context)
		entry = ICourseCatalogEntry(course)
		for name, importer in sorted(component.getUtilitiesFor(ICourseSectionImporter)):
			logger.info("Processing %s", name)
			importer.process(course, filer)
		entry.lastSynchronized = course.lastSynchronized = time.time()

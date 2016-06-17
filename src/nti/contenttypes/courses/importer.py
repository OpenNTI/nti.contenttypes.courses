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
import uuid
import shutil
import tempfile
from hashlib import md5

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

from nti.contentlibrary.filesystem import FilesystemKey

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

from nti.contenttypes.courses.interfaces import SECTIONS
from nti.contenttypes.courses.interfaces import NTI_COURSE_OUTLINE_NODE

from nti.contenttypes.courses.interfaces import iface_of_node

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.contenttypes.courses.interfaces import CourseRolesSynchronized
from nti.contenttypes.courses.interfaces import CourseInstanceImportedEvent
from nti.contenttypes.courses.interfaces import CourseVendorInfoSynchronized

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import clear_course_outline
from nti.contenttypes.courses.utils import get_course_vendor_info
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.internalization import update_from_external_object

from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import make_specific_safe

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

	def course_bucket(self, course):
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s" % (SECTIONS, course.__name__)
		else:
			bucket = None
		return bucket

	def course_bucket_path(self, course):
		bucket = self.course_bucket(course)
		bucket = bucket + "/" if bucket else u''
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

	def makedirs(self, path):
		if path and not os.path.exists(path):
			os.makedirs(path)

@interface.implementer(ICourseSectionImporter)
class CourseOutlineImporter(BaseSectionImporter):

	def make_ntiid(self):
		digest = md5(str(uuid.uuid4())).hexdigest().upper()
		specific = make_specific_safe(TYPE_UUID + ".%s" % digest)
		result = make_ntiid(provider='NTI',
							nttype=NTI_COURSE_OUTLINE_NODE,
							specific=specific)
		return result

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
				if not getattr(node, "ntiid", None):
					node.ntiid = self.make_ntiid()
				registerUtility(registry,
								node,
							  	name=node.ntiid,
							  	provided=iface_of_node(node))
				node.publish(event=False)

			for child in node.values():
				_recur(child)
		_recur(course.Outline)

	def _delete_outline(self, course):
		clear_course_outline(course)
		if ICourseSubInstance.providedBy(course):
			course.prepare_own_outline()

	def process(self, context, filer, writeout=True):
		course = ICourseInstance(context)
		path = self.course_bucket_path(course) + COURSE_OUTLINE_NAME
		source = self.safe_get(filer, path)
		if source is not None:
			# import
			ext_obj = self.load(source)
			self._delete_outline(course)  # not merging
			self._update_and_register(course, ext_obj)

			# save source
			if writeout and IFilesystemBucket.providedBy(course.root):
				source = self.safe_get(filer, path)  # reload
				self.makedirs(course.root.absolute_path)
				new_path = os.path.join(course.root.absolute_path, COURSE_OUTLINE_NAME)
				transfer_to_native_file(source, new_path)

		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class VendorInfoImporter(BaseSectionImporter):

	def process(self, context, filer, writeout=True):
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

			# save source
			if writeout and IFilesystemBucket.providedBy(course.root):
				source = self.safe_get(filer, path)  # reload
				self.makedirs(course.root.absolute_path)
				new_path = os.path.join(course.root.absolute_path, VENDOR_INFO_NAME)
				transfer_to_native_file(source, new_path)

		# process subinstances
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class RoleInfoImporter(BaseSectionImporter):

	def process(self, context, filer, writeout=True):
		course = ICourseInstance(context)
		path = self.course_bucket_path(course) + ROLE_INFO_NAME
		source = self.safe_get(filer, path)
		if source is not None:
			# do import
			source = self.load(source)
			fill_roles_from_json(course, source)
			notify(CourseRolesSynchronized(course))

			# save source
			if writeout and IFilesystemBucket.providedBy(course.root):
				source = self.safe_get(filer, path)  # reload
				self.makedirs(course.root.absolute_path)
				new_path = os.path.join(course.root.absolute_path, ROLE_INFO_NAME)
				transfer_to_native_file(source, new_path)

		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class AssignmentPoliciesImporter(BaseSectionImporter):

	def process(self, context, filer, writeout=True):
		course = ICourseInstance(context)
		path = self.course_bucket_path(course) + ASSIGNMENT_POLICIES_NAME
		source = self.safe_get(filer, path)
		if source is not None:
			# do import
			source = self.load(source)
			fill_asg_from_json(course, source, time.time())

			# save source
			if writeout and IFilesystemBucket.providedBy(course.root):
				source = self.safe_get(filer, path)  # reload
				self.makedirs(course.root.absolute_path)
				new_path = os.path.join(course.root.absolute_path,
										ASSIGNMENT_POLICIES_NAME)
				transfer_to_native_file(source, new_path)

		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class BundlePresentationAssetsImporter(BaseSectionImporter):

	__PA__ = 'presentation-assets'

	def _transfer(self, filer, filer_path, disk_path):
		self.makedirs(disk_path)
		for path in filer.list(filer_path):
			name = filer.key_name(path)
			new_path = os.path.join(disk_path, name)
			if filer.is_bucket(path):
				self._transfer(filer, path, new_path)
			else:
				source = filer.get(path)
				transfer_to_native_file(source, new_path)

	def process(self, context, filer, writeout=True):
		course = ICourseInstance(context)
		root = course.root  # must exists
		if not IFilesystemBucket.providedBy(root) or not writeout:
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

	def process(self, context, filer, writeout=True):
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
		if writeout:
			new_path = os.path.join(root.absolute_path, CATALOG_INFO_NAME)
			transfer_to_native_file(source, new_path)

		path = self.course_bucket_path(course) + DCMETA_FILENAME
		dc_source = self.safe_get(filer, path)
		if writeout and dc_source is not None:
			self.makedirs(root.absolute_path)
			new_path = os.path.join(root.absolute_path, DCMETA_FILENAME)
			transfer_to_native_file(dc_source, new_path)

		tmp_file = None
		try:
			key = root.getChildNamed(CATALOG_INFO_NAME)
			if key is None:
				# CS: We need to save and import the filer source in case
				#  we are creating a course, in which case the catalog 
				# entry object has to be correctly updated
				key = FilesystemKey()
				tmp_file = tempfile.mkstemp()[1]
				key.absolute_path = tmp_file
				transfer_to_native_file(source, tmp_file)

			# process source
			entry = ICourseCatalogEntry(course)
			update_entry_from_legacy_key(entry, key, root, force=True)
		finally:
			if tmp_file is not None: # clean up
				os.remove(tmp_file)

		# process subinstances
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class BundleMetaInfoImporter(BaseSectionImporter):

	def process(self, context, filer, writeout=True):
		course = ICourseInstance(context)
		course = get_parent_course(course)
		root = course.root
		if 		ICourseSubInstance.providedBy(course) \
			or	not IFilesystemBucket.providedBy(root):
			return
		source = self.safe_get(filer, BUNDLE_META_NAME)
		if source is None:
			return

		if writeout: # save on disk
			new_path = os.path.join(root.absolute_path, BUNDLE_META_NAME)
			transfer_to_native_file(source, new_path)

		source = self.safe_get(filer, "bundle_dc_metadata.xml")
		if source is not None and writeout:
			new_path = os.path.join(root.absolute_path, "bundle_dc_metadata.xml")
			transfer_to_native_file(source, new_path)

		# create bundle if required
		created_bundle = created_content_package_bundle(course, root)
		if created_bundle:
			lifecycleevent.created(course.ContentPackageBundle)

		# sync
		tmp_file = None
		try:
			bundle_json_key = root.getChildNamed(BUNDLE_META_NAME)
			if bundle_json_key is None:
				bundle_json_key = FilesystemKey()
				tmp_file = tempfile.mkstemp()[1]
				bundle_json_key.absolute_path = tmp_file
				transfer_to_native_file(source, tmp_file)
			if bundle_json_key is not None:
				sync_bundle_from_json_key(bundle_json_key,
										  course.ContentPackageBundle,
										  dc_meta_name='bundle_dc_metadata.xml',
										  excluded_keys=('ntiid',),
										  dc_bucket=root)
		finally:
			if tmp_file is not None: # clean up
				os.remove(tmp_file)

@interface.implementer(ICourseImporter)
class CourseImporter(object):

	def process(self, context, filer, writeout=True):
		now = time.time()
		course = ICourseInstance(context)
		for name, importer in sorted(component.getUtilitiesFor(ICourseSectionImporter)):
			logger.info("Processing %s", name)
			importer.process(course, filer, writeout)
		entry = ICourseCatalogEntry(course)
		entry.lastSynchronized = course.lastSynchronized = time.time()
		notify(CourseInstanceImportedEvent(course))
		for subinstance in get_course_subinstances(course):
			notify(CourseInstanceImportedEvent(subinstance))
		logger.info("Course %s imported in %s(s)", entry.ntiid, time.time() - now)

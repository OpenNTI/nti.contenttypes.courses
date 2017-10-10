#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import time
import shutil
import tempfile

import simplejson

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.event import notify

from ZODB.interfaces import IConnection

from nti.cabinet.filer import read_source
from nti.cabinet.filer import transfer_to_native_file

from nti.contentlibrary import NTI

from nti.contentlibrary.bundle import BUNDLE_META_NAME
from nti.contentlibrary.bundle import sync_bundle_from_json_key

from nti.contentlibrary.dublincore import DCMETA_FILENAME

from nti.contentlibrary.filesystem import FilesystemKey
from nti.contentlibrary.filesystem import FilesystemBucket

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
from nti.contenttypes.courses.interfaces import CourseSectionImporterExecutedEvent

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import clear_course_outline
from nti.contenttypes.courses.utils import get_course_vendor_info
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.internalization import update_from_external_object

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific

from nti.site.interfaces import IHostPolicyFolder

from nti.site.utils import registerUtility

from nti.traversal.traversal import find_interface

BUNDLE_DC_METADATA = "bundle_dc_metadata.xml"

logger = __import__('logging').getLogger(__name__)


def makedirs(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


@interface.implementer(ICourseSectionImporter)
class BaseSectionImporter(object):

    def _prepare(self, data):
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return data

    def load(self, source):
        data = read_source(source)
        return simplejson.loads(self._prepare(data))

    def course_bucket(self, course):
        if ICourseSubInstance.providedBy(course):
            bucket = "%s/%s" % (SECTIONS, course.__name__)
        else:
            bucket = None
        return bucket

    def course_bucket_path(self, course):
        bucket = self.course_bucket(course)
        bucket = bucket + "/" if bucket else ''
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
        makedirs(path)


@interface.implementer(ICourseSectionImporter)
class CourseOutlineImporter(BaseSectionImporter):

    def make_ntiid(self, parent, idx):
        if ICourseOutline.providedBy(parent):
            course = find_interface(parent, ICourseInstance, strict=False)
            entry = ICourseCatalogEntry(course)
            base = entry.ntiid
        else:
            base = parent.ntiid

        provider = get_provider(base) or NTI
        specific_base = get_specific(base)
        specific = specific_base + u".%s" % idx
        ntiid = make_ntiid(nttype=NTI_COURSE_OUTLINE_NODE,
                           base=base,
                           provider=provider,
                           specific=specific)
        return ntiid

    def _update_and_register(self, course, ext_obj):
        # require connection
        connection = IConnection(course)

        def _object_hook(unused_k, v, unused_x):
            if      ICourseOutlineNode.providedBy(v) \
                and not ICourseOutline.providedBy(v):
                connection.add(v)
            return v
        update_from_external_object(course.Outline,
                                    ext_obj,
                                    notify=False,
                                    object_hook=_object_hook)

        # get site registry
        folder = find_interface(course, IHostPolicyFolder, strict=False)
        registry = folder.getSiteManager()

        # register nodes
        def _recur(node, idx=0):
            if not ICourseOutline.providedBy(node):
                if not getattr(node, "ntiid", None):
                    parent = node.__parent__
                    node.ntiid = self.make_ntiid(parent, idx)
                    parent.rename(node.__name__, node.ntiid)

                registerUtility(registry,
                                node,
                                name=node.ntiid,
                                provided=iface_of_node(node))

            for idx, child in enumerate(node.values()):
                _recur(child, idx)
        _recur(course.Outline)

    def _delete_outline(self, course):
        if ICourseSubInstance.providedBy(course):
            parent_course = get_parent_course(course)
            # Only clear our outline if we're not shared currently.
            if course.Outline is not parent_course.Outline:
                clear_course_outline(course)
            course.prepare_own_outline()
        else:
            clear_course_outline(course)

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
                for name in (COURSE_OUTLINE_NAME, 'course_outline.xml'):
                    path = self.course_bucket_path(course) + name
                    source = self.safe_get(filer, path)  # reload
                    if source is not None:
                        self.makedirs(course.root.absolute_path)
                        new_path = os.path.join(course.root.absolute_path,
                                                name)
                        transfer_to_native_file(source, new_path)

        for sub_instance in get_course_subinstances(course):
            self.process(sub_instance, filer, writeout=writeout)


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
                new_path = os.path.join(course.root.absolute_path,
                                        VENDOR_INFO_NAME)
                transfer_to_native_file(source, new_path)

        # process subinstances
        for sub_instance in get_course_subinstances(course):
            self.process(sub_instance, filer, writeout=writeout)


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
                new_path = os.path.join(
                    course.root.absolute_path, ROLE_INFO_NAME)
                transfer_to_native_file(source, new_path)
        # process subinstances
        for sub_instance in get_course_subinstances(course):
            self.process(sub_instance, filer, writeout=writeout)


@interface.implementer(ICourseSectionImporter)
class AssignmentPoliciesImporter(BaseSectionImporter):

    def process(self, context, filer, writeout=True):
        course = ICourseInstance(context)
        path = self.course_bucket_path(course) + ASSIGNMENT_POLICIES_NAME
        source = self.safe_get(filer, path)
        if source is not None:
            # do import
            source = self.load(source)
            fill_asg_from_json(course, source, time.time(), force=True)
            # save source
            if writeout and IFilesystemBucket.providedBy(course.root):
                source = self.safe_get(filer, path)  # reload
                self.makedirs(course.root.absolute_path)
                new_path = os.path.join(course.root.absolute_path,
                                        ASSIGNMENT_POLICIES_NAME)
                transfer_to_native_file(source, new_path)

        for sub_instance in get_course_subinstances(course):
            self.process(sub_instance, filer, writeout=writeout)


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
            self.process(sub_instance, filer, writeout=writeout)


@interface.implementer(ICourseSectionImporter)
class CourseInfoImporter(BaseSectionImporter):

    def process(self, context, filer, writeout=True):
        course = ICourseInstance(context)
        course.SharingScopes.initScopes()
        entry = ICourseCatalogEntry(course)
        # make sure Discussions are initialized
        getattr(course, 'Discussions')

        root = course.root  # must exists
        if not IFilesystemBucket.providedBy(root):
            return
        if not getattr(entry, 'root', None):
            entry.root = root

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

        tmp_dir = None
        try:
            key = root.getChildNamed(CATALOG_INFO_NAME)
            if key is None:
                tmp_dir = tempfile.mkdtemp()
                # save CATALOG_INFO_NAME
                tmp_cat_info = os.path.join(tmp_dir, CATALOG_INFO_NAME)
                transfer_to_native_file(source, tmp_cat_info)
                key = FilesystemKey()
                key.absolute_path = tmp_cat_info
                # save DCMETA_FILENAME
                if dc_source != None:
                    tmp_dc_meta = os.path.join(tmp_dir, DCMETA_FILENAME)
                    transfer_to_native_file(dc_source, tmp_dc_meta)
                    root = FilesystemBucket()
                    root.absolute_path = tmp_dir
                    root.key = os.path.split(tmp_dir)[1]
            # process source(s)
            entry = ICourseCatalogEntry(course)
            update_entry_from_legacy_key(entry, key, root, force=True)
        finally:
            if tmp_dir is not None:  # clean up
                shutil.rmtree(tmp_dir)

        # process subinstances
        for sub_instance in get_course_subinstances(course):
            self.process(sub_instance, filer, writeout=writeout)


@interface.implementer(ICourseSectionImporter)
class BundleMetaInfoImporter(BaseSectionImporter):

    def _to_fs_key(self, source, path, name):
        result = FilesystemKey()
        self.makedirs(path)  # create
        out_path = os.path.join(path, name)
        result.absolute_path = out_path
        transfer_to_native_file(source, out_path)
        return result

    def process(self, context, filer, writeout=True):
        course = ICourseInstance(context)
        course = get_parent_course(course)
        root = course.root
        if     ICourseSubInstance.providedBy(course) \
            or not IFilesystemBucket.providedBy(root):
            return
        name_source = self.safe_get(filer, BUNDLE_META_NAME)
        if name_source is None:
            return

        if writeout:  # save on disk
            new_path = os.path.join(root.absolute_path, BUNDLE_META_NAME)
            transfer_to_native_file(name_source, new_path)

        dc_source = self.safe_get(filer, BUNDLE_DC_METADATA)
        if dc_source is not None and writeout:
            new_path = os.path.join(root.absolute_path, BUNDLE_DC_METADATA)
            transfer_to_native_file(dc_source, new_path)

        # create bundle if required
        created_bundle = created_content_package_bundle(course, root)
        if created_bundle:
            lifecycleevent.created(course.ContentPackageBundle)

        # sync
        tmp_dir = None
        try:
            update_bundle = True
            bundle_json_key = root.getChildNamed(BUNDLE_META_NAME)
            dc_meta_json_key = root.getChildNamed(BUNDLE_DC_METADATA)
            if bundle_json_key is None:
                # create a tmp directory root for bundle files
                tmp_dir = tempfile.mkdtemp()
                # XXX copy bundle files to new temp root
                bundle_json_key = self._to_fs_key(name_source,
                                                  tmp_dir,
                                                  BUNDLE_META_NAME)
                if dc_meta_json_key is None:
                    self._to_fs_key(dc_source, tmp_dir, BUNDLE_DC_METADATA)
                else:
                    self._to_fs_key(dc_meta_json_key,
                                    tmp_dir,
                                    BUNDLE_DC_METADATA)
                # XXX new import root temp
                update_bundle = False
                root = FilesystemBucket()
                root.absolute_path = tmp_dir
                root.key = os.path.split(tmp_dir)[1]

            sync_bundle_from_json_key(bundle_json_key,
                                      course.ContentPackageBundle,
                                      dc_meta_name=BUNDLE_DC_METADATA,
                                      excluded_keys=('ntiid',),
                                      dc_bucket=root,
                                      update_bundle=update_bundle)
        finally:
            if tmp_dir is not None:  # clean up
                shutil.rmtree(tmp_dir)


@interface.implementer(ICourseImporter)
class CourseImporter(object):

    def makedirs(self, path):
        makedirs(path)

    def _mark_sync(self, context):
        now = time.time()
        for provided in (ICourseInstance, ICourseCatalogEntry):
            try:
                provided(context).lastSynchronized = now
            except AttributeError:
                pass

    def process(self, context, filer, writeout=True):
        now = time.time()
        course = ICourseInstance(context)
        if      writeout \
            and not ICourseSubInstance.providedBy(course) \
            and IFilesystemBucket.providedBy(course.root):
            self.makedirs(course.root.absolute_path)
        for name, importer in sorted(component.getUtilitiesFor(ICourseSectionImporter)):
            current = time.time()
            logger.info("Processing %s", name)
            try:
                importer.process(course, filer, writeout)
                notify(CourseSectionImporterExecutedEvent(course, importer, filer, writeout))
                logger.info("%s processed in %s(s)", name, time.time() - current)
            except Exception as e:
                logger.exception("Error while processing %s", name)
                raise e
        # notify
        self._mark_sync(course)
        notify(CourseInstanceImportedEvent(course))
        for subinstance in get_course_subinstances(course):
            self._mark_sync(subinstance)
            notify(CourseInstanceImportedEvent(subinstance))
        result = time.time() - now
        logger.info("Course %s imported in %s(s)",
                    ICourseCatalogEntry(course).ntiid, result)
        return result

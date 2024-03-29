#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Code to synchronize course-catalog folders with the disk. This also
defines the on-disk layout.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.container.contained import Contained

from zope.event import notify

from zope.intid.interfaces import IIntIds

from zope.lifecycleevent import ObjectModifiedEvent

from zope.site.interfaces import ILocalSiteManager

from nti.base._compat import text_

from nti.contentlibrary.bundle import BUNDLE_META_NAME
from nti.contentlibrary.bundle import sync_bundle_from_json_key

from nti.contentlibrary.interfaces import IDelimitedHierarchyKey
from nti.contentlibrary.interfaces import IDelimitedHierarchyBucket

from nti.contenttypes.courses._assessment_override_parser import fill_asg_from_key
from nti.contenttypes.courses._assessment_override_parser import reset_asg_missing_key

from nti.contenttypes.courses._assessment_policy_validator import validate_assigment_policies

from nti.contenttypes.courses._bundle import created_content_package_bundle

from nti.contenttypes.courses._catalog_entry_parser import update_entry_from_legacy_key

from nti.contenttypes.courses._enrollment import update_deny_open_enrollment
from nti.contenttypes.courses._enrollment import check_enrollment_mapped_course

from nti.contenttypes.courses._evaluation_parser import fill_evaluations_from_key

from nti.contenttypes.courses._outline_parser import fill_outline_from_key

from nti.contenttypes.courses._role_parser import fill_roles_from_key

from nti.contenttypes.courses._sharing_scopes import update_sharing_scopes_friendly_names

from nti.contenttypes.courses import ROLE_INFO_NAME
from nti.contenttypes.courses import EVALUATION_INDEX
from nti.contenttypes.courses import VENDOR_INFO_NAME
from nti.contenttypes.courses import CATALOG_INFO_NAME
from nti.contenttypes.courses import GRADING_POLICY_NAME
from nti.contenttypes.courses import ASSIGNMENT_DATES_NAME

from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel

from nti.contenttypes.courses.discussions.parser import parse_discussions

from nti.contenttypes.courses.grading import fill_grading_policy_from_key

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import COURSE_OUTLINE_NAME
from nti.contenttypes.courses.interfaces import SECTIONS as SECTION_FOLDER_NAME
from nti.contenttypes.courses.interfaces import DISCUSSIONS as DISCUSSION_FOLDER_NAME

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSubInstances
from nti.contenttypes.courses.interfaces import IDenyOpenEnrollment
from nti.contenttypes.courses.interfaces import IObjectEntrySynchronizer
from nti.contenttypes.courses.interfaces import IContentCourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseSynchronizationResults
from nti.contenttypes.courses.interfaces import IDoNotCreateDefaultOutlineCourseInstance

from nti.contenttypes.courses.interfaces import CourseRolesSynchronized
from nti.contenttypes.courses.interfaces import CatalogEntrySynchronized
from nti.contenttypes.courses.interfaces import CourseBundleWillUpdateEvent
from nti.contenttypes.courses.interfaces import CourseInstanceAvailableEvent
from nti.contenttypes.courses.interfaces import CourseVendorInfoSynchronized

from nti.dataserver.interfaces import ISharingTargetEntityIterable

from nti.externalization.representation import WithRepr

from nti.intid.common import addIntId

from nti.schema.eqhash import EqHash

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

logger = __import__('logging').getLogger(__name__)


@WithRepr
@EqHash('NTIID')
@interface.implementer(ICourseSynchronizationResults)
class CourseSynchronizationResults(SchemaConfigured, Contained):
    createDirectFieldProperties(ICourseSynchronizationResults)


def _site_name(registry=None):
    registry = component.getSiteManager() if registry is None else registry
    if ILocalSiteManager.providedBy(registry):
        result = registry.__parent__.__name__
    else:
        result = getattr(registry, '__name__', None)
    return text_(result)


def _get_sync_ntiids(**kwargs):
    params = kwargs.get('params')  # sync params
    ntiids = params.packages if params is not None else ()
    ntiids = ntiids if isinstance(ntiids, set) else set(ntiids)
    return ntiids


def _get_sync_results(**kwargs):
    return kwargs.get('results')


def _get_course_sync_results(context, sync_results=None, **kwargs):
    if sync_results is None:
        entry = ICourseCatalogEntry(context)
        sync_results = CourseSynchronizationResults(NTIID=entry.ntiid,
                                                    Site=_site_name())
        results = _get_sync_results(**kwargs)
        if results is not None:
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
        """
        Pull in any new levels/courses into our db. We no longer
        remove anything during sync since we may now have API
        created data.
        """
        # Find the things in the filesystem
        child_buckets = dict()
        for item in bucket.enumerateChildren():
            if IDelimitedHierarchyBucket.providedBy(item):
                child_buckets[item.__name__] = item

        # Create anything the folder is missing if we have a factory for it
        for bucket_child_name in child_buckets:
            # pylint: disable=unused-variable
            __traceback_info__ = folder, bucket, bucket_child_name
            child_bucket = child_buckets[bucket_child_name]
            factory = self._get_factory_for(child_bucket)
            folder_obj = folder.get(bucket_child_name, None)

            if      folder_obj is not None \
                and factory is not None \
                and not isinstance(folder_obj, factory) \
                and isinstance(folder_obj, self._ADMIN_LEVEL_FACTORY):
                # Probably converting from administrative level to course, because
                # (in error), this object was probably accidentally set up as admin level
                # and it was intended to be a course. We will only allow conversion from
                # admin levels to courses.
                logger.warn('Type of course folder structure changed (name=%s) (old=%s) (new=%s), will convert',
                            bucket_child_name,
                            type(folder_obj),
                            factory)
                folder_obj = None
                del folder[bucket_child_name]

            if folder_obj is None and factory is not None:
                new_child_object = factory()
                new_child_object.root = child_bucket
                # Fire the added event
                __traceback_info__ = folder, child_bucket, new_child_object
                if ICourseInstance.providedBy(new_child_object):
                    interface.alsoProvides(new_child_object,
                                           IDoNotCreateDefaultOutlineCourseInstance)
                folder[bucket_child_name] = new_child_object

        # Synchronize everything
        for child_name, child in folder.items():
            try:
                child_bucket = child_buckets[child_name]
            except KeyError:
                pass
            else:
                sync = component.getMultiAdapter((child, child_bucket),
                                                 IObjectEntrySynchronizer)
                sync.synchronize(child, child_bucket, **kwargs)


@interface.implementer(IObjectEntrySynchronizer)
@component.adapter(ICourseInstance, IDelimitedHierarchyBucket)
class _ContentCourseSynchronizer(object):

    def __init__(self, course, bucket):
        pass

    def synchronize(self, course, bucket, force=False, **kwargs):
        # pylint: disable=unused-variable
        __traceback_info__ = course, bucket
        entry = ICourseCatalogEntry(course)

        # gather sync params
        ntiids = _get_sync_ntiids(**kwargs)

        # First, synchronize the bundle
        bundle_json_key = bucket.getChildNamed(BUNDLE_META_NAME)
        if not IDelimitedHierarchyKey.providedBy(bundle_json_key):  # pragma: no cover
            raise ValueError("No bundle defined for course", course, bucket)

        # Check if we need to sync
        if ntiids and entry.ntiid not in ntiids:
            return

        # prepare sync results
        sync_results = _get_course_sync_results(entry, **kwargs)

        created_bundle = created_content_package_bundle(course, bucket)
        bundle = course.ContentPackageBundle

        # The catalog entry gets the default DublinCore metadata file name,
        # in this bucket, since it really describes the data.
        # The content bundle, on the other hand, gets a custom file
        old_packages = set(bundle.ContentPackages)
        modified = sync_bundle_from_json_key(bundle_json_key,
                                             course.ContentPackageBundle,
                                             dc_meta_name='bundle_dc_metadata.xml',
                                             excluded_keys=('ntiid',))

        if modified:
            logger.info("Updating course bundle (%s)", entry.ntiid)
            new_packages = set(bundle.ContentPackages)
            added_packages = new_packages - old_packages
            removed_packages = old_packages - new_packages
            notify(CourseBundleWillUpdateEvent(course, added_packages, removed_packages))
            # pylint: disable=attribute-defined-outside-init
            sync_results.ContentBundleUpdated = True

        if created_bundle:
            lifecycleevent.added(bundle)

        self.update_common_info(course, bucket,
                                sync_results=sync_results,
                                try_legacy_content_bundle=True,
                                force=force)

        self.update_deny_open_enrollment(course)

        self.update_site_manager(course, bucket, sync_results=sync_results)

        notify(CourseInstanceAvailableEvent(course, bucket,
                                            _get_sync_results(**kwargs)))

        sections_bucket = bucket.getChildNamed(SECTION_FOLDER_NAME)
        sync = component.getMultiAdapter((course.SubInstances, sections_bucket))
        sync.synchronize(course.SubInstances, sections_bucket, **kwargs)

        # After we've loaded all the sections, check to see if we should map
        # enrollment
        check_enrollment_mapped_course(course)

        # mark last sync time
        course.lastSynchronized = entry.lastSynchronized = time.time()

        return sync_results

    @classmethod
    def update_common_info(cls, course, bucket,
                           sync_results=None,
                           try_legacy_content_bundle=False,
                           force=False):
        sync_results = _get_course_sync_results(course, sync_results)

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

        cls.update_outline(course=course,
                           bucket=bucket,
                           sync_results=sync_results,
                           try_legacy_content_bundle=try_legacy_content_bundle,
                           force=force)

        cls.update_catalog_entry(course=course,
                                 bucket=bucket,
                                 sync_results=sync_results,
                                 try_legacy_content_bundle=try_legacy_content_bundle)

        cls.update_vendor_info(course, bucket, sync_results)

        cls.update_instructor_roles(course, bucket, sync_results=sync_results)
        cls.update_assignment_policies(course, bucket,
                                       sync_results=sync_results)

        # make sure Discussions are initialized
        getattr(course, 'Discussions')
        cls.update_sharing_scopes_friendly_names(course,
                                                 sync_results=sync_results)

        # validate assigment policies
        cls.validate_assigment_policies(course, bucket)

        # update course evaluations
        cls.update_course_evaluations(course, bucket)

        # check grading policy. it must be done after validating assigments
        cls.update_grading_policy(course, bucket, sync_results=sync_results)

        # update dicussions
        cls.update_course_discussions(course, bucket)

    @classmethod
    def update_sharing_scopes_friendly_names(cls, course, sync_results=None):
        sync_results = _get_course_sync_results(course, sync_results)
        scopes = update_sharing_scopes_friendly_names(course)
        if scopes:
            # pylint: disable=attribute-defined-outside-init
            sync_results.SharingScopesUpdated = True

    @classmethod
    def update_vendor_info(cls, course, bucket, sync_results=None):
        sync_results = _get_course_sync_results(course, sync_results)
        vendor_json_key = bucket.getChildNamed(VENDOR_INFO_NAME)
        vendor_info = ICourseInstanceVendorInfo(course)
        not_empty = bool(vendor_info)
        # pylint: disable=attribute-defined-outside-init,too-many-function-args
        if not vendor_json_key:
            vendor_info.clear()
            vendor_info.createdTime = 0
            vendor_info.lastModified = 0
            sync_results.VendorInfoReseted = not_empty
        elif vendor_json_key.lastModified > vendor_info.lastModified:
            vendor_info.clear()
            vendor_info.update(vendor_json_key.readContentsAsJson())
            vendor_info.createdTime = vendor_json_key.createdTime
            vendor_info.lastModified = vendor_json_key.lastModified
            sync_results.VendorInfoUpdated = True

        if sync_results.VendorInfoReseted or sync_results.VendorInfoUpdated:
            notify(CourseVendorInfoSynchronized(course))

    @classmethod
    def update_outline(cls, course, bucket, sync_results=None,
                       try_legacy_content_bundle=False,
                       force=False):
        sync_results = _get_course_sync_results(course, sync_results)

        outline_xml_node = None
        outline_xml_key = bucket.getChildNamed(COURSE_OUTLINE_NAME)
        if not outline_xml_key and try_legacy_content_bundle:
            # Only want to do this for root courses
            if course.ContentPackageBundle:
                # Just take the first one. That should be all there
                # is in legacy cases
                for package in course.ContentPackageBundle.ContentPackages:
                    outline_xml_key = package.index
                    outline_xml_node = u'course'
                    break

        # pylint: disable=attribute-defined-outside-init,protected-access
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
                                     force=force,
                                     sync_results=sync_results):
                sync_results.OutlineUpdated = True

    @classmethod
    def update_catalog_entry(cls, course, bucket, sync_results=None,
                             try_legacy_content_bundle=False):
        sync_results = _get_course_sync_results(course, sync_results)
        catalog_json_key = bucket.getChildNamed(CATALOG_INFO_NAME)
        if not catalog_json_key and try_legacy_content_bundle:
            # Only want to do this for root courses
            if course.ContentPackageBundle:
                for package in course.ContentPackageBundle.ContentPackages:
                    if package.does_sibling_entry_exist(CATALOG_INFO_NAME):
                        catalog_json_key = package.make_sibling_key(
                            CATALOG_INFO_NAME)
                        break

        modified = False
        catalog_entry = ICourseCatalogEntry(course)
        intids = component.queryUtility(IIntIds)
        if intids is not None and intids.queryId(catalog_entry) is None:
            addIntId(catalog_entry)
        if catalog_json_key:
            modified = update_entry_from_legacy_key(catalog_entry,
                                                    catalog_json_key,
                                                    bucket=bucket)
        if modified:
            # pylint: disable=attribute-defined-outside-init
            notify(CatalogEntrySynchronized(catalog_entry))
            notify(ObjectModifiedEvent(catalog_entry))
            sync_results.CatalogEntryUpdated = True

    @classmethod
    def update_instructor_roles(cls, course, bucket, sync_results=None):
        sync_results = _get_course_sync_results(course, sync_results)
        role_json_key = bucket.getChildNamed(ROLE_INFO_NAME)
        if role_json_key:
            if fill_roles_from_key(course, role_json_key):
                # pylint: disable=attribute-defined-outside-init
                notify(CourseRolesSynchronized(course))
                sync_results.InstructorRolesUpdated = True

    @classmethod
    def update_assignment_policies(cls, course, bucket, sync_results=None):
        sync_results = _get_course_sync_results(course, sync_results)
        key = bucket.getChildNamed(ASSIGNMENT_DATES_NAME)
        # pylint: disable=attribute-defined-outside-init
        if key is not None:
            if fill_asg_from_key(course, key):
                sync_results.AssignmentPoliciesUpdated = True
        elif reset_asg_missing_key(course):
            sync_results.AssignmentPoliciesReseted = True

    @classmethod
    def update_course_evaluations(cls, course, bucket, sync_results=None):
        sync_results = _get_course_sync_results(course, sync_results)
        key = bucket.getChildNamed(EVALUATION_INDEX)
        if key is not None:
            if fill_evaluations_from_key(course, key):
                # pylint: disable=attribute-defined-outside-init
                sync_results.EvaluationsUpdated = True

    @classmethod
    def update_grading_policy(cls, course, bucket, sync_results=None):
        # We no longer wipe existing policies out.
        sync_results = _get_course_sync_results(course, sync_results)
        key = bucket.getChildNamed(GRADING_POLICY_NAME)
        if      key is not None \
            and fill_grading_policy_from_key(course, key):
            # pylint: disable=attribute-defined-outside-init
            sync_results.GradingPolicyUpdated = True

    @classmethod
    def validate_assigment_policies(cls, course, unused_bucket):
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
        update_deny_open_enrollment(course)

    @classmethod
    def update_course_discussions(cls, course, bucket, sync_results=None):
        sync_results = _get_course_sync_results(course, sync_results)
        key = bucket.getChildNamed(DISCUSSION_FOLDER_NAME)
        if key is not None and IDelimitedHierarchyBucket.providedBy(key):
            result = parse_discussions(course, key)
            # pylint: disable=attribute-defined-outside-init
            sync_results.CourseDiscussionsUpdated = result

    @classmethod
    def update_site_manager(cls, course, bucket=None, sync_results=None):
        pass


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

    def synchronize(self, instances, *unused_args, **unused_kwargs):
        instances.clear()


@interface.implementer(IObjectEntrySynchronizer)
@component.adapter(IContentCourseSubInstance, IDelimitedHierarchyBucket)
class _ContentCourseSubInstanceSynchronizer(object):

    def __init__(self, subcourse, bucket):
        pass

    def synchronize(self, subcourse, bucket, force=False, **kwargs):
        # pylint: disable=unused-variable
        __traceback_info__ = subcourse, bucket

        course_sync_results = _get_course_sync_results(subcourse, **kwargs)

        _ContentCourseSynchronizer.update_common_info(subcourse, bucket,
                                                      sync_results=course_sync_results,
                                                      force=force)

        _ContentCourseSynchronizer.update_deny_open_enrollment(subcourse)

        _ContentCourseSynchronizer.update_site_manager(subcourse, bucket)

        # mark last sync time
        entry = ICourseCatalogEntry(subcourse)
        subcourse.lastSynchronized = entry.lastSynchronized = time.time()

        notify(CourseInstanceAvailableEvent(subcourse,
                                            bucket,
                                            _get_sync_results(**kwargs)))

        return course_sync_results


def synchronize_catalog_from_root(catalog_folder, root, **kwargs):
    """
    Given a :class:`CourseCatalogFolder` and a class:`.IDelimitedHierarchyBucket`,
    synchronize the course catalog to match.
    """
    synchronizer = component.getMultiAdapter((catalog_folder, root),
                                             IObjectEntrySynchronizer)
    synchronizer.synchronize(catalog_folder, root, **kwargs)

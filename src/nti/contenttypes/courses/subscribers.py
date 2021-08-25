#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zc.intid.interfaces import IBeforeIdRemovedEvent

from zope import component
from zope import lifecycleevent

from zope.component.hooks import site

from zope.event import notify

from zope.security.management import queryInteraction

from zope.intid.interfaces import IIntIds
from zope.intid.interfaces import IIntIdAddedEvent

from zope.interface.interfaces import IRegistered
from zope.interface.interfaces import IUnregistered

from zope.lifecycleevent import ObjectModifiedEvent

from zope.lifecycleevent.interfaces import IObjectCreatedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IUnlockQAssessmentPolicies
from nti.assessment.interfaces import IQAssessmentPoliciesModified
from nti.assessment.interfaces import IQAssessmentDateContextModified

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageAddedEvent
from nti.contentlibrary.interfaces import IContentPackageRemovedEvent
from nti.contentlibrary.interfaces import IPersistentContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageLibraryDidSyncEvent
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses._enrollment import update_deny_open_enrollment

from nti.contenttypes.courses.common import get_course_packages
from nti.contenttypes.courses.common import get_course_site_name
from nti.contenttypes.courses.common import get_course_site_registry

from nti.contenttypes.courses.catalog import CourseCatalogFolder

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import IX_COURSE
from nti.contenttypes.courses.index import IX_USERNAME
from nti.contenttypes.courses.index import IX_PACKAGES

from nti.contenttypes.courses.index import IndexRecord

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import COURSE_CATALOG_NAME
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_NAMES
from nti.contenttypes.courses.interfaces import TRX_OUTLINE_NODE_MOVE_TYPE

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IContentCourseInstance
from nti.contenttypes.courses.interfaces import ICourseRoleRemovedEvent
from nti.contenttypes.courses.interfaces import ICourseEditorAddedEvent
from nti.contenttypes.courses.interfaces import ICourseRolesUpdatedEvent
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import IObjectEntrySynchronizer
from nti.contenttypes.courses.interfaces import ICourseRolesSynchronized
from nti.contenttypes.courses.interfaces import IPersistentCourseCatalog
from nti.contenttypes.courses.interfaces import CourseBundleUpdatedEvent
from nti.contenttypes.courses.interfaces import CourseCatalogDidSyncEvent
from nti.contenttypes.courses.interfaces import ICourseBundleUpdatedEvent
from nti.contenttypes.courses.interfaces import CourseBundleWillUpdateEvent
from nti.contenttypes.courses.interfaces import ICourseInstructorAddedEvent
from nti.contenttypes.courses.interfaces import ICourseBundleWillUpdateEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceImportedEvent
from nti.contenttypes.courses.interfaces import ICourseOutlineNodeMovedEvent
from nti.contenttypes.courses.interfaces import ICourseRolePermissionManager
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent
from nti.contenttypes.courses.interfaces import ICourseVendorInfoSynchronized
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.interfaces import iface_of_node

from nti.contenttypes.courses.utils import unenroll 
from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import index_course_roles
from nti.contenttypes.courses.utils import index_course_editor
from nti.contenttypes.courses.utils import get_courses_catalog
from nti.contenttypes.courses.utils import clear_course_outline
from nti.contenttypes.courses.utils import unindex_course_roles
from nti.contenttypes.courses.utils import get_course_hierarchy
from nti.contenttypes.courses.utils import index_course_instance
from nti.contenttypes.courses.utils import index_course_instructor
from nti.contenttypes.courses.utils import get_content_unit_courses
from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import remove_principal_from_course_content_roles

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import IFriendlyNamed
from nti.dataserver.users.interfaces import RealnameInvalid

from nti.externalization.interfaces import IObjectModifiedFromExternalEvent

from nti.intid.common import addIntId
from nti.intid.common import removeIntId

from nti.metadata import queue_metadata_modififed

from nti.recorder.utils import record_transaction

from nti.site.localutility import install_utility
from nti.site.localutility import uninstall_utility_on_unregistration

from nti.site.utils import registerUtility

logger = __import__('logging').getLogger(__name__)


# This is very similar to nti.contentlibrary.subscribers


@component.adapter(IPersistentContentPackageLibrary, IRegistered)
def install_site_course_catalog(local_library, _=None):
    """
    When a new local site, representing a site (host) policy
    is added, install a site-local course-catalog and associated utilities
    into it. The catalog is sync'd after this is done.

    If you need to perform work, such as registering your own
    utility in the local site that uses the local catalog, listen for the component
    registration event, :class:`zope.interface.interfaces.IRegistered`,
    which is an ObjectEvent, whose object will be an
    :class:`nti.contenttypes.courses.interfaces.IPersistentCourseCatalog`.

    Although this function is ordinarily called as an event listener
    for a :class:`.IRegistered` event for a
    :class:`.IPersistentContentPackageLibrary`, it can also be called
    manually, passing in just a site manager. In that case, if there
    is no local course catalog, and one can now be found, it will be
    created; if a local catalog already exists, nothing will be done.

    :returns: The site local catalog, if one was found or installed.
    """

    # We take either a local library, which will be in the context
    # of a site manager, or the site manager itself, which
    # is directly adaptable to IComponentLookup
    # (zope.component.hooks tries to adapt context to IComponentLookup,
    # and zope.site.site contains a SiteManagerAdapter that walks
    # up the parent tree)
    local_site_manager = component.getSiteManager(local_library)

    # Don't import a message factory
    if _ is None and COURSE_CATALOG_NAME in local_site_manager:
        cat = local_site_manager[COURSE_CATALOG_NAME]
        logger.debug("Nothing to do for site %s, catalog already present %s",
                     local_site_manager, cat)
        return cat

    # pylint: disable=no-member
    local_site = local_site_manager.__parent__
    assert bool(local_site.__name__), "sites must be named"

    catalog = CourseCatalogFolder()

    with site(local_site):
        # install in this site so the right utilities and event
        # listeners are found
        # Before we install (which fires a registration event that things might
        # be listening for) set up the dependent utilities
        install_utility(catalog,
                        COURSE_CATALOG_NAME,
                        IPersistentCourseCatalog,
                        local_site_manager)

        # Note that it is not safe to sync if we got here as the result
        # of the registration event...that can lead to cycles,
        # because the library syncs itself on registration. wait for
        # that event.
        if _ is None:
            if not IPersistentContentPackageLibrary.providedBy(local_library):
                # because we cold have been handed the site
                local_library = local_site_manager.getUtility(IContentPackageLibrary)
            sync_catalog_when_library_synched(local_library, None)
        return catalog


@component.adapter(IPersistentContentPackageLibrary, IUnregistered)
def uninstall_site_course_catalog(unused_library, event):
    uninstall_utility_on_unregistration(COURSE_CATALOG_NAME,
                                        IPersistentCourseCatalog,
                                        event)


# Sync-related subscribers


@component.adapter(IPersistentContentPackageLibrary,
                   IContentPackageLibraryDidSyncEvent)
def sync_catalog_when_library_synched(library, event):
    """
    When a persistent content library is synchronized
    with the disk contents, whether or not anything actually changed,
    we also synchronize the corresponding course catalog. (Because they could
    change independently and in unknown ways)
    """
    # sync params/results
    params = event.params
    results = event.results

    # Find the local site manager
    site_manager = component.getSiteManager(library)
    if library.__parent__ is not site_manager:
        msg =  "Expected to find persistent library in its own site; refusing to sync"
        logger.warn(msg)
        return

    catalog = site_manager.get(COURSE_CATALOG_NAME)
    if catalog is None:
        logger.info("Installing and synchronizing course catalog for %s",
                    site_manager)
        # which in turn will call back to us
        install_site_course_catalog(library)
        return
    # pylint: disable=no-member
    enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
    enumeration_root = enumeration.root
    courses_bucket = enumeration_root.getChildNamed(catalog.__name__)
    if courses_bucket is None:
        logger.warning(
            "Not synchronizing: no directory named %s in %s for catalog %s",
            catalog.__name__,
            getattr(enumeration_root, 'absolute_path', enumeration_root),
            catalog)
        return

    logger.info("Synchronizing course catalog %s in site %s from directory %s",
                catalog, site_manager.__parent__.__name__,
                getattr(courses_bucket, 'absolute_path', courses_bucket))

    synchronizer = component.getMultiAdapter((catalog, courses_bucket),
                                             IObjectEntrySynchronizer)
    synchronizer.synchronize(catalog,
                             courses_bucket,
                             params=params,
                             results=results)

    # Course catalog has been synced
    notify(CourseCatalogDidSyncEvent(catalog, params, results))


@component.adapter(ICourseInstance, ICourseRolesSynchronized)
def roles_sync_on_course_instance(course, unused_event=None):
    catalog = get_enrollment_catalog()
    intids = component.queryUtility(IIntIds)
    if catalog is not None and intids is not None:
        unindex_course_roles(course, catalog)
        indexed_count = index_course_roles(course,
                                           catalog=catalog,
                                           intids=intids)
        entry = ICourseCatalogEntry(course, None)
        entry_ntiid = entry.ntiid if entry is not None else ''
        logger.info('Indexed %s roles for %s',
                    indexed_count, entry_ntiid)

@component.adapter(ICourseInstance, ICourseRolesSynchronized)
def index_course_on_course_roles_synced(course, unused_event):
    # After role synchronized, indexing instructors/editors in the courses catalog.
    index_course_instance(course)


@component.adapter(ICourseInstance, ICourseVendorInfoSynchronized)
def on_course_vendor_info_synced(course, unused_event=None):
    catalog = get_courses_catalog()
    intids = component.queryUtility(IIntIds)
    doc_id = intids.queryId(course) if intids is not None else None
    if doc_id is not None:
        catalog.index_doc(doc_id, course)
    update_deny_open_enrollment(course)


@component.adapter(IUser, IObjectRemovedEvent)
def on_user_removed(user, unused_event=None):
    logger.info('Removing enrollment records for %s', user.username)
    catalog = get_enrollment_catalog()
    if catalog is not None:
        intids = component.getUtility(IIntIds)
        # remove enrollment records
        query = {
            IX_USERNAME: {'any_of': (user.username,)},
            IX_SCOPE: {'any_of': ENROLLMENT_SCOPE_NAMES}
        }
        for uid in catalog.apply(query) or ():
            record = intids.queryObject(uid)
            if ICourseInstanceEnrollmentRecord.providedBy(record):
                unenroll(record, user)
            catalog.unindex_doc(uid)
        # remove instructor/ editor roles
        index = catalog[IX_USERNAME]
        query = {
            IX_USERNAME: {'any_of': (user.username,)},
        }
        for uid in catalog.apply(query) or ():
            record = IndexRecord(user.username)
            index.remove(uid, record)  # KeepSet index
    # TODO: update course catalog


def remove_enrollment_records(course):
    # pylint: disable=too-many-function-args
    manager = ICourseEnrollmentManager(course)
    return manager.drop_all()


def unindex_enrollment_records(course):
    catalog = get_enrollment_catalog()
    site_name = get_course_site_name(course)
    entry = ICourseCatalogEntry(course, None)
    ntiid = getattr(entry, 'ntiid', None)
    if catalog is not None and ntiid and site_name:
        query = {
            IX_COURSE: {'any_of': (ntiid,)},
            IX_SITE: {'any_of': (site_name,)},
        }
        for uid in catalog.apply(query) or ():
            catalog.unindex_doc(uid)


@component.adapter(ICourseInstance, IBeforeIdRemovedEvent)
def on_before_course_instance_removed(course, unused_event=None):
    intids = component.getUtility(IIntIds)
    entry = ICourseCatalogEntry(course, None)
    if entry is not None and intids.queryId(entry) is not None:
        removeIntId(entry)


@component.adapter(ICourseInstance, IObjectCreatedEvent)
def on_course_instance_created(course, unused_event=None):
    intids = component.queryUtility(IIntIds)
    entry = ICourseCatalogEntry(course, None)
    if      entry is not None \
        and intids is not None \
        and intids.queryId(entry) is None:
        addIntId(entry)


@component.adapter(ICourseInstance, IObjectRemovedEvent)
def on_course_instance_removed(course, unused_event=None):
    # remove enrollment records
    remove_enrollment_records(course)
    unindex_enrollment_records(course)
    # clear outline
    if     not ICourseSubInstance.providedBy(course) \
        or course.Outline != get_parent_course(course).Outline:
        clear_course_outline(course)
    # For section course instructors, remove access to the parent
    # course if they are not also a parent course instructor.
    # XXX: It is possible this logic is duplicated and handled
    # in the util functions we call below which gather other
    # courses the user is an instructor in.
    if ICourseSubInstance.providedBy(course):
        parent_course = get_parent_course(course)
        parent_course_instructors = parent_course.instructors or ()
        for section_inst in course.instructors or ():
            if section_inst not in parent_course_instructors:
                section_inst = IUser(section_inst, None)
                # Check if the instructor was deleted.
                if section_inst is not None:
                    section_inst = User.get_user(section_inst.username)

                if section_inst is None:
                    continue
                remove_principal_from_course_content_roles(section_inst, course, unenroll=True)
                public_scope = parent_course.SharingScopes[ES_PUBLIC]
                section_inst.record_no_longer_dynamic_member(public_scope)
                section_inst.stop_following(public_scope)
    # remove bundle
    if      not ICourseSubInstance.providedBy(course) \
        and IContentCourseInstance.providedBy(course) \
        and course.ContentPackageBundle is not None:
        lifecycleevent.removed(course.ContentPackageBundle)


def course_default_roles(course):
    course_role_manager = ICourseRolePermissionManager(course)
    if course_role_manager is not None:
        # pylint: disable=too-many-function-args
        course_role_manager.initialize()


@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def on_course_instance_available(course, unused_event=None):
    course_default_roles(course)


@component.adapter(ICourseInstance, ICourseInstanceImportedEvent)
def on_course_instance_imported(course, unused_event=None):
    course_default_roles(course)


@component.adapter(ICourseOutlineNode, ICourseOutlineNodeMovedEvent)
def on_course_outline_node_moved(node, event):
    ntiid = getattr(node, 'ntiid', None)
    if ntiid and not ICourseOutline.providedBy(node):
        record_transaction(node, principal=event.principal,
                           type_=TRX_OUTLINE_NODE_MOVE_TYPE)


@component.adapter(ICourseOutlineNode, IIntIdAddedEvent)
def on_course_outline_node_added(node, unused_event=None):
    ntiid = getattr(node, 'ntiid', None)
    if ntiid and not ICourseOutline.providedBy(node):
        registry = get_course_site_registry(node)
        if registry is None:
            registry = component.getSiteManager()
        provided = iface_of_node(node)
        if registry.queryUtility(provided, name=ntiid) is None:
            registerUtility(registry,
                            node,
                            provided=iface_of_node(node),
                            name=ntiid)


def _lock_assessment_policy(event, course=None):
    assesment = event.assesment
    context = event.object if course is None else course
    course = ICourseInstance(context, None)  # adapt to a course
    if course is not None and assesment:
        # pylint: disable=too-many-function-args
        policies = IQAssessmentPolicies(course)
        policies.set(assesment, 'locked', True)
        # log message
        entry = ICourseCatalogEntry(course)
        assesment = getattr(assesment, 'ntiid', assesment)
        logger.info("%s in course %s has been locked",
                    assesment, entry.ntiid)


@component.adapter(IQAssessmentPoliciesModified)
def on_assessment_policy_modified(event):
    _lock_assessment_policy(event)


@component.adapter(IQAssessmentDateContextModified)
def on_assessment_date_context_modified(event):
    _lock_assessment_policy(event)


def _unlock_assessment_policy(assesment, courses=()):
    courses = [courses] if ICourseInstance.providedBy(courses) else courses
    for course in courses or ():
        course = ICourseInstance(course, None)
        if course is not None:
            # pylint: disable=too-many-function-args
            policies = IQAssessmentPolicies(course)
            policies.remove(assesment, 'locked')
            entry = ICourseCatalogEntry(course)
            assesment = getattr(assesment, 'ntiid', assesment)
            logger.info("%s in course %s has been unlocked",
                        assesment, entry.ntiid)


@component.adapter(IUnlockQAssessmentPolicies)
def on_unlock_assessment_policies(event):
    if event.courses and event.object:
        _unlock_assessment_policy(event.object, event.courses)


@component.adapter(ICourseInstance, ICourseBundleWillUpdateEvent)
def _update_course_packages(root_course, event=None):
    """
    Update the course packages
    """
    catalog = get_courses_catalog()
    if catalog is not None:  # tests
        index = catalog[IX_PACKAGES]
        intids = component.getUtility(IIntIds)
        courses = get_course_hierarchy(root_course)
        # The bundle is shared between all course hierarchy members.
        for course in courses:
            doc_id = intids.queryId(course)
            if doc_id is not None:
                index.index_doc(doc_id, course)
    # Once our index is up-to-date, we can notify that the bundle
    # has been updated.
    if event is not None:
        notify(CourseBundleUpdatedEvent(root_course,
                                        event.added_packages,
                                        event.removed_packages))
update_course_packages = _update_course_packages


@component.adapter(ICourseInstance, ICourseBundleUpdatedEvent)
def _on_course_bundle_updated(course, unused_event=None):
    """
    The course packages have been updated.
    """
    if hasattr(course, 'ContentPackageBundle'):
        lifecycleevent.modified(course.ContentPackageBundle)


@component.adapter(ICourseInstance, ICourseInstanceImportedEvent)
def _on_course_imported(course, unused_event=True):
    _update_course_packages(course)
    _on_course_bundle_updated(course)
on_course_imported = _on_course_imported


@component.adapter(IContentPackage, IContentPackageAddedEvent)
def _update_course_bundle(new_package, unused_event=True):
    """
    With content package added, make sure we update our state
    (index, permissions, etc) in case we have a bundle wref
    already pointing to the package.
    """
    if queryInteraction() is not None:
        return
    # Have to iterate through since our index may not have this package.
    # This may be expensive if triggered interactively.
    catalog = component.getUtility(ICourseCatalog)
    for entry in catalog.iterCatalogEntries():
        course = ICourseInstance(entry, None)
        packages = get_course_packages(course)
        if packages and new_package in packages:
            # A content package has been added, fire since our
            # bundle has essentially been updated.
            logger.info('Updating course bundle with new package (%s) (%s)',
                        new_package.ntiid, entry.ntiid)
            notify(CourseBundleWillUpdateEvent(course, (new_package,)))


@component.adapter(IContentPackage, IContentPackageRemovedEvent)
def _update_course_bundle_on_package_removal(package, unused_event=True):
    """
    When a content package is deleted, remove it from the
    appropriate courses.
    """
    courses = get_content_unit_courses(package)
    for course in courses or ():
        entry = ICourseCatalogEntry(course)
        logger.info('Removing package from course (%s) (%s)',
                    package.ntiid, entry.ntiid)
        course.ContentPackageBundle.remove(package)
        notify(CourseBundleWillUpdateEvent(course, removed_packages=(package,)))


@component.adapter(IUser, ICourseInstructorAddedEvent)
def on_course_instructor_added(user, event):
    index_course_instructor(user, event.course)


@component.adapter(IUser, ICourseEditorAddedEvent)
def on_course_editor_added(user, event):
    index_course_editor(user, event.course)


@component.adapter(ICourseRolesUpdatedEvent)
def on_course_roles_updated(event):
    unindex_course_roles(event.object)
    index_course_roles(event.object)


@component.adapter(IUser, ICourseRoleRemovedEvent)
def on_course_role_removed(unused_user, event):
    # On role removed, we need to re-index our course.
    unindex_course_roles(event.course)
    index_course_roles(event.course)


@component.adapter(ICourseCatalogEntry, IObjectModifiedFromExternalEvent)
def _update_scopes_on_course_title_change(entry, unused_event):
    """
    We can always update the scopes realname here. We should
    not allow any API changes to these realnames.
    """
    if not entry.title:
        return
    course = ICourseInstance(entry, None)
    if course is None:
        return
    course_title = entry.title
    for scope in course.SharingScopes.values():
        friendly_named = IFriendlyNamed(scope, None)
        if friendly_named is None:
            continue
        scope_name = scope.__name__
        new_name = course_title if scope_name == ES_PUBLIC else '%s (%s)' % (course_title, scope_name)
        try:
            friendly_named.realname = new_name
        except RealnameInvalid:
            # Most likely a public scope for a symbol-named course
            friendly_named.realname = '%s-course' % course_title
        notify(ObjectModifiedEvent(scope))


@component.adapter(ICourseCatalogEntry, IObjectModifiedFromExternalEvent)
def _update_sections_on_tag_update(entry, event):
    """
    When parent course tags are updated, notify for child course entry iff shared.
    This is to update the tag index for these section courses.
    """
    if event.external_value and 'tags' in event.external_value:
        parent_tags = entry.tags
        parent_course = ICourseInstance(entry)
        for section_course in get_course_subinstances(parent_course):
            section_entry = ICourseCatalogEntry(section_course)
            # Section entry tags are acquired from the parent if not
            # distinct.
            if section_entry.tags is parent_tags:
                notify(ObjectModifiedEvent(section_entry))
            

def _update_enrollment_meta(record):
    """
    On an enrollment added or removed, we want to send our
    course to update its metadata.
    We do not want to just notify cause that may cause conflicts
    on the in process catalog.
    """
    queue_metadata_modififed(record.CourseInstance)


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectCreatedEvent)
def _update_meta_on_enrollment_created(record, unused_event):
    _update_enrollment_meta(record)


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectRemovedEvent)
def _update_meta_on_enrollment_removed(record, unused_event):
    _update_enrollment_meta(record)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$

 TODO: Add support for AWS
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import time
import shutil

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.annotation.interfaces import IAnnotations

from zope.component.hooks import getSite

from zope.intid.interfaces import IIntIds

from nti.coremetadata.utils import current_principal

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contentlibrary.interfaces import IFilesystemBucket
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses import EVALUATION_INDEX_LAST_MODIFIED

from nti.contenttypes.courses._bundle import created_content_package_bundle

from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel

from nti.contenttypes.courses.interfaces import SECTIONS

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICreatedCourse
from nti.contenttypes.courses.interfaces import IContentCourseInstance
from nti.contenttypes.courses.interfaces import CourseAlreadyExistsException

from nti.intid.common import addIntId

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.traversal.traversal import find_interface

from nti.zodb.containers import time_to_64bit_int

logger = __import__('logging').getLogger(__name__)


def create_annotations(course):
    annotations = IAnnotations(course)
    annotations[EVALUATION_INDEX_LAST_MODIFIED] = 0


def create_directory(path):
    if path and not os.path.exists(path):
        os.mkdir(path)


def make_directories(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


def delete_directory(path):
    if path and os.path.exists(path):
        shutil.rmtree(path, True)


def course_catalog(catalog):
    if catalog is None:
        catalog = component.getUtility(ICourseCatalog)
    return catalog


def library_root():
    library = component.getUtility(IContentPackageLibrary)
    enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
    return enumeration.root


def _get_course_bucket(catalog, site):
    enumeration_root = library_root()
    courses_bucket = enumeration_root.getChildNamed(catalog.__name__)
    if courses_bucket is None:
        path = os.path.join(enumeration_root.absolute_path, catalog.__name__)
        make_directories(path)
        courses_bucket = enumeration_root.getChildNamed(catalog.__name__)
        logger.info('[%s] Creating Courses dir in site',
                    getattr(site, '__name__', None))
    return courses_bucket


def install_admin_level(admin_name, catalog=None, site=None, writeout=True, parents=True):
    site = getSite() if site is None else site
    catalog = course_catalog(catalog)
    courses_bucket = _get_course_bucket(catalog, site)
    logger.info('[%s] Creating admin level %s',
                getattr(site, '__name__', None),
                admin_name)
    admin_root = courses_bucket.getChildNamed(admin_name)
    if admin_root is None and IFilesystemBucket.providedBy(courses_bucket):
        path = os.path.join(courses_bucket.absolute_path, admin_name)
        if writeout:
            make_directories(path)
            admin_root = courses_bucket.getChildNamed(admin_name)
        else:
            admin_root = FilesystemBucket()
            admin_root.key = admin_name
            admin_root.bucket = courses_bucket
            admin_root.absolute_path = path
    # Create admin level; do not want to overwrite parent catalog levels.
    if admin_name not in catalog.get_admin_levels(parents):
        result = CourseAdministrativeLevel()
        result.root = admin_root
        catalog[admin_name] = result
    else:
        result = catalog[admin_name]
    return result
create_admin_level = install_admin_level


def _create_bundle_ntiid(bundle, ntiid_type):
    """
    Create a bundle ntiid without us relying on our hierarchical path.
    """
    course = find_interface(bundle, ICourseInstance, strict=False)
    entry = ICourseCatalogEntry(course, None)
    if not getattr(entry, 'ntiid', None):
        intids = component.queryUtility(IIntIds)
        current_time = time_to_64bit_int(time.time())
        if intids is not None:
            addIntId(bundle)
            bundle_id = intids.getId(bundle)
            specific_base = '%s.%s' % (bundle_id, current_time)
        else:
            specific_base = str(current_time)
        specific = make_specific_safe(specific_base)
        ntiid = make_ntiid(nttype=ntiid_type,
                           specific=specific)
    else:
        specific = get_specific(entry.ntiid)
        ntiid = make_ntiid(nttype=ntiid_type,
                           base=entry.ntiid,
                           specific=specific)
    return ntiid


def _prepare_entry(course):
    entry = ICourseCatalogEntry(course)
    intids = component.queryUtility(IIntIds)
    if intids is not None and intids.queryId(entry) is None:
        addIntId(entry)
    # make sure ntiid is initialized
    getattr(entry, 'ntiid')


def create_course(admin, key, catalog=None, writeout=False,
                  strict=False, creator=None, factory=ContentCourseInstance):
    """
    Creates a course

    :param admin Administrative level key
    :param key Course name
    :param strict If True, raises an error when the key already exists,
    otherwise returns the existing course by default.
    """
    if not key:
        raise ValueError("Must specify a course name")
    if not admin:
        raise ValueError("Must specify an administrative level key")

    catalog = course_catalog(catalog)
    if admin not in catalog:
        install_admin_level(admin, catalog, writeout=writeout)

    administrative_level = catalog[admin]
    root = administrative_level.root
    if root is None:
        raise IOError("Administrative level does not have a root bucket")

    writeout = writeout and IFilesystemBucket.providedBy(root)
    if getattr(root, 'absolute_path', None):
        course_path = os.path.join(root.absolute_path, key)
    else:
        course_path = None
        writeout = False  # there is not absolute_path

    if writeout and IFilesystemBucket.providedBy(root):
        create_directory(course_path)

    course_root = root.getChildNamed(key)
    if course_root is None:
        if not writeout and IFilesystemBucket.providedBy(root):
            course_root = FilesystemBucket()
            course_root.key = key
            course_root.bucket = root
            course_root.absolute_path = course_path
        else:
            raise IOError("Could not access course bucket %s", course_path)

    if key in administrative_level:
        if strict:
            msg = "Course with key %s already exists" % key
            raise CourseAlreadyExistsException(msg)
        course = administrative_level[key]
        logger.debug("Course '%s' already created", key)
    else:
        course = factory()
        course.root = course_root
        administrative_level[key] = course  # gain intid
        # initialize catalog entry
        _prepare_entry(course)
        # make sure annotations are created to get a connection
        create_annotations(course)
        # mark & set creator
        creator = creator or current_principal().id
        interface.alsoProvides(course, ICreatedCourse)
        course.creator = creator
        getattr(course, 'Discussions')
        getattr(course, 'SharingScopes')
        lifecycleevent.created(course)
        # create a bundle
        if IContentCourseInstance.providedBy(course):
            created_content_package_bundle(course, course_root,
                                           ntiid_factory=_create_bundle_ntiid)
    return course


def create_course_subinstance(course, name, writeout=False, creator=None,
                              factory=ContentCourseSubInstance):
    """
    Creates a course subinstance

    :param course Parent course
    :param name subinstance name
    """
    sub_section_root = None
    course_root = course.root
    if IFilesystemBucket.providedBy(course_root):
        course_path = course_root.absolute_path
        # create sections path
        sections_path = os.path.join(course_path, SECTIONS)
        if writeout:
            create_directory(sections_path)
        sections_root = course_root.getChildNamed(SECTIONS)
        if sections_root is None:
            sections_root = FilesystemBucket()
            sections_root.key = SECTIONS
            sections_root.bucket = course_root
            sections_root.absolute_path = sections_path
        # create subinstance path
        subinstance_section_path = os.path.join(sections_path, name)
        if writeout:
            create_directory(subinstance_section_path)
        # get chained root
        sub_section_root = sections_root.getChildNamed(name)
        if sub_section_root is None:
            sub_section_root = FilesystemBucket()
            sub_section_root.key = name
            sub_section_root.bucket = sections_root
            sub_section_root.absolute_path = subinstance_section_path
    # create object
    if name not in course.SubInstances:
        subinstance = factory()
        subinstance.root = sub_section_root
        course.SubInstances[name] = subinstance
        # initialize catalog entry
        _prepare_entry(course)
        # mark & set creator
        creator = creator or current_principal().id
        interface.alsoProvides(subinstance, ICreatedCourse)
        subinstance.creator = creator
        # make sure annotations are created to get a connection
        create_annotations(subinstance)
        getattr(course, 'Discussions')
        getattr(course, 'SharingScopes')
        lifecycleevent.created(course)
    else:
        subinstance = course.SubInstances[name]
    return subinstance

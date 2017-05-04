#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$

 TODO: Add support for AWS
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import shutil

from zope import component

from zope.component.hooks import getSite

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contentlibrary.interfaces import IFilesystemBucket
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel

from nti.contenttypes.courses.interfaces import SECTIONS
from nti.contenttypes.courses.interfaces import ICourseCatalog


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


def install_admin_level(admin_name, catalog=None, site=None, writeout=True):
    site = getSite() if site is None else site
    enumeration_root = library_root()

    catalog = course_catalog(catalog)
    courses_bucket = enumeration_root.getChildNamed(catalog.__name__)

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
    # Create admin level
    if admin_name not in catalog:
        result = CourseAdministrativeLevel()
        result.root = admin_root
        catalog[admin_name] = result
    else:
        result = catalog[admin_name]
    return result
create_admin_level = install_admin_level


def create_course(admin, key, catalog=None, writeout=False, factory=ContentCourseInstance):
    """
    Creates a course

    :param admin Administrative level key
    :param key Course name
    """
    catalog = course_catalog(catalog)
    if admin not in catalog:
        install_admin_level(admin, catalog)

    administrative_level = catalog[admin]
    root = administrative_level.root
    if root is None:
        raise IOError("Administrative level does not have a root bucket")

    writeout = writeout and IFilesystemBucket.providedBy(root)
    course_path = os.path.join(root.absolute_path, key)
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
        course = administrative_level[key]
        logger.debug("Course '%s' already created", key)
    else:
        course = factory()
        course.root = course_root
        administrative_level[key] = course  # gain intid
    return course


def create_course_subinstance(course, name, writeout=False, factory=ContentCourseSubInstance):
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
    else:
        subinstance = course.SubInstances[name]
    return subinstance

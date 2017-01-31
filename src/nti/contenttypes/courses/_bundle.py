#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import string_types

from zope import interface
from zope import lifecycleevent

from nti.contentlibrary.bundle import PersistentContentPackageBundle

from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.legacy_catalog import _ntiid_from_entry

from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle

from nti.ntiids.ntiids import find_object_with_ntiid


@interface.implementer(ICourseContentPackageBundle)
class CoursePersistentContentPackageBundle(PersistentContentPackageBundle):

    mime_type = mimeType = 'application/vnd.nextthought.coursecontentpackagebundle'

    def add(self, context):
        if not isinstance(context, string_types):
            context = find_object_with_ntiid(context)
        assert context is IContentPackage
        return PersistentContentPackageBundle.add(self, context)

    def remove(self, context):
        if not isinstance(context, string_types):
            context = find_object_with_ntiid(context)
        assert context is IContentPackage
        return PersistentContentPackageBundle.remove(self, context)


def created_content_package_bundle(course, bucket=None):
    created_bundle = False
    if course.ContentPackageBundle is None:
        bundle = CoursePersistentContentPackageBundle()
        bundle.root = bucket
        bundle.__parent__ = course
        bundle.createdTime = bundle.lastModified = 0
        bundle.ntiid = _ntiid_from_entry(bundle, 'Bundle:CourseBundle')
        # register w/ course and notify
        course.ContentPackageBundle = bundle
        lifecycleevent.created(bundle)
        created_bundle = True
    return created_bundle

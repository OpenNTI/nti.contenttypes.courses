#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from six import string_types

from zope import component
from zope import interface
from zope import lifecycleevent

from nti.contentlibrary.bundle import PersistentContentPackageBundle

from nti.contentlibrary.externalization import ContentBundleIO

from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses import COURSE_BUNDLE_TYPE

from nti.contenttypes.courses.legacy_catalog import _ntiid_from_entry

from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.wref.interfaces import IWeakRef

ITEMS = StandardExternalFields.ITEMS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseContentPackageBundle)
class CoursePersistentContentPackageBundle(PersistentContentPackageBundle):

    mime_type = mimeType = 'application/vnd.nextthought.coursecontentpackagebundle'

    def _is_valid_type(self, obj):
        return IContentPackage.providedBy(obj) \
            or IWeakRef.providedBy(obj)

    def add(self, context):
        if isinstance(context, string_types):
            context = find_object_with_ntiid(context)
        assert self._is_valid_type(context)
        return PersistentContentPackageBundle.add(self, context)

    def remove(self, context):
        if isinstance(context, string_types):
            context = find_object_with_ntiid(context)
        assert self._is_valid_type(context)
        return PersistentContentPackageBundle.remove(self, context)


def created_content_package_bundle(course, bucket=None,
                                   ntiid_factory=_ntiid_from_entry):
    created_bundle = False
    if course.ContentPackageBundle is None:
        bundle = CoursePersistentContentPackageBundle()
        bundle.root = bucket or course.root
        bundle.createdTime = bundle.lastModified = 0
        # set lineage before ntiid
        bundle.__parent__ = course
        bundle.ntiid = ntiid_factory(bundle, COURSE_BUNDLE_TYPE)
        # register w/ course and notify
        course.ContentPackageBundle = bundle
        lifecycleevent.created(bundle)
        created_bundle = True
    return created_bundle


@component.adapter(ICourseContentPackageBundle)
class _CourseContentBundleIO(ContentBundleIO):

    _ext_iface_upper_bound = ICourseContentPackageBundle

    _excluded_in_ivars_ = getattr(ContentBundleIO, '_excluded_in_ivars_').union(
        {'ntiid'}
    )

    validate_packages = True

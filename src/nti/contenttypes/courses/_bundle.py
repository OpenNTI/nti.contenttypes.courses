#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import string_types

from zope import component
from zope import interface
from zope import lifecycleevent

from nti.contentlibrary.bundle import PersistentContentPackageBundle

from nti.contentlibrary.externalization import ContentBundleIO

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.legacy_catalog import _ntiid_from_entry

from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

ITEMS = StandardExternalFields.ITEMS


@interface.implementer(ICourseContentPackageBundle)
class CoursePersistentContentPackageBundle(PersistentContentPackageBundle):

    mime_type = mimeType = 'application/vnd.nextthought.coursecontentpackagebundle'

    def add(self, context):
        if isinstance(context, string_types):
            context = find_object_with_ntiid(context)
        assert IContentPackage.providedBy(context)
        return PersistentContentPackageBundle.add(self, context)

    def remove(self, context):
        if isinstance(context, string_types):
            context = find_object_with_ntiid(context)
        assert IContentPackage.providedBy(context)
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


@component.adapter(ICourseContentPackageBundle)
class _CourseContentBundleIO(ContentBundleIO):

    _ext_iface_upper_bound = ICourseContentPackageBundle

    _excluded_in_ivars_ = getattr(ContentBundleIO, '_excluded_in_ivars_').union(
        {'ntiid', 'root', 'ContentPackages'})

    @classmethod
    def resolve(cls, ntiid, library):
        paths = library.pathToNTIID(ntiid) if library is not None else None
        return paths[0] if paths else None

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        result = InterfaceObjectIO.updateFromExternalObject(self, parsed)
        items = parsed.get('ContentPackages') or parsed.get(ITEMS)
        library = component.queryUtility(IContentPackageLibrary)
        if items is not None:
            packages = []
            for ntiid in items:
                package = self.resolve(ntiid, library)
                if package is None:
                    raise KeyError("Cannot find content package", ntiid)
                packages.append(package)
            self._ext_self.ContentPackages = packages
            result = True
        return result

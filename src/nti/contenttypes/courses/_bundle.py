#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import lifecycleevent

from nti.contentlibrary.bundle import PersistentContentPackageBundle

from nti.contenttypes.courses.legacy_catalog import _ntiid_from_entry


def created_content_package_bundle(course, bucket=None):
    created_bundle = False
    if course.ContentPackageBundle is None:
        bundle = PersistentContentPackageBundle()
        bundle.root = bucket
        bundle.__parent__ = course
        bundle.createdTime = bundle.lastModified = 0
        bundle.ntiid = _ntiid_from_entry(bundle, 'Bundle:CourseBundle')
        # register w/ course and notify
        course.ContentPackageBundle = bundle
        lifecycleevent.created(bundle)
        created_bundle = True
    return created_bundle

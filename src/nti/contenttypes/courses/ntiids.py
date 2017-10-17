#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import NTIID_ENTRY_TYPE

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import IContentCourseInstance

from nti.ntiids.interfaces import INTIIDResolver

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import find_object_with_ntiid

logger = __import__('logging').getLogger(__name__)


@interface.implementer(INTIIDResolver)
class _CourseInfoNTIIDResolver(object):
    """
    Resolves course info ntiids through the catalog.
    """

    def resolve(self, ntiid):
        catalog = component.queryUtility(ICourseCatalog)
        try:
            return catalog.getCatalogEntry(ntiid)
        except (AttributeError, KeyError):
            pass
        return None


@interface.implementer(INTIIDResolver)
class _CourseOutlineNodeNTIIDResolver(object):
    """
    Resolves outline nodes
    """

    def resolve(self, ntiid):
        result = component.queryUtility(ICourseOutlineNode, name=ntiid)
        return result


@interface.implementer(INTIIDResolver)
class _CourseBundleNTIIDResolver(object):
    """
    Resolves course bundles
    """

    def resolve(self, ntiid):
        ntiid = make_ntiid(nttype=NTIID_ENTRY_TYPE, base=ntiid)
        course = IContentCourseInstance(find_object_with_ntiid(ntiid), None)
        if course is not None:
            return course.ContentPackageBundle
        return None

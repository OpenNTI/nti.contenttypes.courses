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

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope

from nti.contenttypes.courses.legacy_catalog import ICourseCatalogInstructorLegacyInfo

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.externalization.singleton import Singleton

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

MIMETYPE = StandardExternalFields.MIMETYPE

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseOutlineNode)
@interface.implementer(IExternalObjectDecorator)
class _CourseOutlineNodeDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        if not original.LessonOverviewNTIID:
            external.pop('LessonOverviewNTIID', None)
        if 'ntiid' not in external and getattr(original, 'ntiid', None):
            external['ntiid'] = original.ntiid


@component.adapter(ICourseOutline)
@interface.implementer(IExternalObjectDecorator)
class _CourseOutlineDecorator(Singleton):

    def decorateExternalObject(self, unused_original, external):
        external.pop('publishEnding', None)
        external.pop('publishBeginning', None)


@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseCatalogInstructorLegacyInfo)
class _InstructorLegacyInfoDecorator(Singleton):

    def decorateExternalObject(self, unused_original, external):
        external.pop('userid', None)


@component.adapter(ICourseInstanceSharingScope)
@interface.implementer(IExternalObjectDecorator)
class _CourseInstanceSharingScopeDecorator(Singleton):

    def decorateExternalObject(self, unused_original, external):
        # XXX: For BWC w/ clients
        external[MIMETYPE] = 'application/vnd.nextthought.community'


@interface.implementer(IExternalObjectDecorator)
class _CourseNonPublicStatusDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        if 'is_non_public' not in external:
            is_non_public = INonPublicCourseInstance.providedBy(original)
            external['is_non_public'] = is_non_public


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _CourseAdminLevelDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        course = ICourseInstance(original, None)
        if course is not None:
            admin = find_interface(course, ICourseAdministrativeLevel, strict=False)
            if admin is not None:
                external['AdminLevel'] = admin.__name__


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _CourseSiteDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        course = ICourseInstance(original, None)
        if course is not None:
            site = find_interface(course, IHostPolicyFolder, strict=False)
            if site is not None:
                external['Site'] = site.__name__


@component.adapter(ICourseContentPackageBundle)
@interface.implementer(IExternalObjectDecorator)
class _CourseBundleDecorator(Singleton):
    """
    The client apparently uses the bundle title as a proxy to the course title.
    With edits, these may fall out of sync. Should we always overwrite?
    """

    def decorateExternalObject(self, original, external):
        title = external['title']
        if not title:
            course = ICourseInstance(original, None)
            entry = ICourseCatalogEntry(course, None)
            entry_title = getattr(entry, 'title', '')
            if entry_title:
                external['title'] = entry_title

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
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope

from nti.contenttypes.courses.legacy_catalog import ICourseCatalogInstructorLegacyInfo

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.externalization.singleton import Singleton

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
        external[MIMETYPE] = 'application/vnd.nextthought.community'


@interface.implementer(IExternalObjectDecorator)
class _CourseNonPublicStatusDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        if 'is_non_public' not in external:
            external['is_non_public'] = INonPublicCourseInstance.providedBy(original)

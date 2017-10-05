#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import six

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope

from nti.contenttypes.courses.legacy_catalog import ICourseCatalogInstructorLegacyInfo

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.externalization.singleton import SingletonMetaclass

MIMETYPE = StandardExternalFields.MIMETYPE

logger = __import__('logging').getLogger(__name__)


@six.add_metaclass(SingletonMetaclass)
@component.adapter(ICourseOutlineNode)
@interface.implementer(IExternalObjectDecorator)
class _CourseOutlineNodeDecorator(object):

    def __init__(self, *args):
        pass

    def decorateExternalObject(self, original, external):
        if not original.LessonOverviewNTIID:
            external.pop('LessonOverviewNTIID', None)
        if 'ntiid' not in external and getattr(original, 'ntiid', None):
            external['ntiid'] = original.ntiid


@six.add_metaclass(SingletonMetaclass)
@component.adapter(ICourseOutline)
@interface.implementer(IExternalObjectDecorator)
class _CourseOutlineDecorator(object):

    def __init__(self, *args):
        pass

    def decorateExternalObject(self, unused_original, external):
        external.pop('publishEnding', None)
        external.pop('publishBeginning', None)


@six.add_metaclass(SingletonMetaclass)
@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseCatalogInstructorLegacyInfo)
class _InstructorLegacyInfoDecorator(object):

    def __init__(self, *args):
        pass

    def decorateExternalObject(self, unused_original, external):
        external.pop('userid', None)


@six.add_metaclass(SingletonMetaclass)
@component.adapter(ICourseInstanceSharingScope)
@interface.implementer(IExternalObjectDecorator)
class _CourseInstanceSharingScopeDecorator(object):

    def __init__(self, *args):
        pass

    def decorateExternalObject(self, unused_original, external):
        external[MIMETYPE] = 'application/vnd.nextthought.community'


@six.add_metaclass(SingletonMetaclass)
@interface.implementer(IExternalObjectDecorator)
class _CourseNonPublicStatusDecorator(object):

    def __init__(self, *args):
        pass

    def decorateExternalObject(self, original, external):
        if 'is_non_public' not in external:
            external['is_non_public'] = INonPublicCourseInstance.providedBy(original)

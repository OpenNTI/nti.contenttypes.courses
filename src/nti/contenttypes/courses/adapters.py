#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from collections import Mapping

from datetime import datetime

import six

from zope import component
from zope import interface

from zope.annotation.factory import factory as an_factory

from zope.traversing.api import traverse

from nti.common.iterables import is_nonstr_iterable

from nti.contenttypes.completion.interfaces import ICompletionContext

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseKeywords
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseImportMetadata
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_vendor_info

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(IHostPolicyFolder)
def _course_to_site(context):
    return find_interface(context, IHostPolicyFolder, strict=False)


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IHostPolicyFolder)
def _entry_to_site(context):
    return _course_to_site(ICourseInstance(context, None))


@component.adapter(ICourseOutlineNode)
@interface.implementer(ICourseInstance)
def _outlinenode_to_course(outline):
    outline = find_interface(outline, ICourseOutline, strict=False)
    outline = getattr(outline, 'aq_base', outline)
    return find_interface(outline, ICourseInstance, strict=False)


@interface.implementer(ICourseInstance)
@component.adapter(ICourseContentPackageBundle)
def _bundle_to_course(bundle):
    return find_interface(bundle, ICourseInstance, strict=False)


@component.adapter(ICourseCatalogEntry)
@interface.implementer(ICompletionContext)
def _entry_to_completion_context(context):
    return ICourseInstance(context, None)

# keywords


class _Keywords(object):

    __slots__ = ('keywords',)

    def __init__(self, keywords=()):
        self.keywords = keywords


def _keyword_gatherer(data):
    result = set()
    if isinstance(data, six.string_types):
        result.update(data.split())
    elif is_nonstr_iterable(data):
        for value in data:
            result.update(_keyword_gatherer(value))
    elif isinstance(data, Mapping):
        for key, value in data.items():
            result.add(key)
            result.update(_keyword_gatherer(value))
    elif data is not None:
        result.add(str(data))
    result = tuple(x.strip() for x in result if x)
    return result


def _invitation_gatherer(data):
    result = set()
    if isinstance(data, six.string_types):
        result.update(data.split())
    elif is_nonstr_iterable(data):
        for value in data:
            if isinstance(value, six.string_types):
                result.add(value)
            elif isinstance(value, Mapping):
                code = value.get('code') or value.get('Code')
                result.add(code)
    result = tuple(x.strip() for x in result if x)
    return result


def _names(course):
    result = None
    if course is not None:
        result = set()
        level = find_interface(course,
                               ICourseAdministrativeLevel,
                               strict=False)
        if level is not None:
            result.add(level.__name__)  # admin level
        parent = get_parent_course(course)
        result.add(parent.__name__)  # course name
        if ICourseSubInstance.providedBy(course):
            result.add(course.__name__)
            result.add('SubInstance')
        entry = ICourseCatalogEntry(course, None)
        if entry is not None:
            result.add(entry.ProviderUniqueID)
        result.discard('')
        result.discard(None)
    return tuple(x.strip() for x in result or () if x)


@component.adapter(ICourseInstance)
@interface.implementer(ICourseKeywords)
def _course_keywords(context):
    result = set()
    info = get_course_vendor_info(context, create=False) or {}
    # keyword and tags
    for path in ('NTI/Keywords', 'NTI/Tags'):
        data = traverse(info, path, default=None)
        result.update(_keyword_gatherer(data))
    # invitation codes
    data = traverse(info, 'NTI/Invitations', default=None)
    result.update(_invitation_gatherer(data))
    # paths
    result.update(_names(ICourseInstance(context, None)))
    # clean and return
    result.discard('')
    result.discard(None)
    return _Keywords(sorted(result))


@component.adapter(ICourseInstance)
@interface.implementer(ICourseImportMetadata)
class _CourseImportMetadata(object):

    _import_hash = None
    last_import_time = None

    @property
    def import_hash(self):
        return self._import_hash

    @import_hash.setter
    def import_hash(self, new_import_hash):
        self._import_hash = new_import_hash
        self.last_import_time = datetime.utcnow()


COURSE_IMPORT_METADATA_KEY = 'nti.contenttypes.courses.import.CourseImportMetadata'
CourseImportMetadataFactory = an_factory(_CourseImportMetadata,
                                         key=COURSE_IMPORT_METADATA_KEY)

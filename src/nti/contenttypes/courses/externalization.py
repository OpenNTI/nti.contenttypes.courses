#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from collections import Mapping

from zope import component
from zope import interface

from zope.security.interfaces import IPrincipal

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseTabPreferences
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance

from nti.dataserver.interfaces import ILinkExternalHrefOnly
from nti.dataserver.interfaces import IUseNTIIDAsExternalUsername

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields
from nti.externalization.interfaces import IInternalObjectExternalizer

from nti.links.links import Link

from nti.mimetype.externalization import decorateMimeType

from nti.namedfile.file import safe_filename

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import is_ntiid_of_type
from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.traversal.traversal import find_interface

ID = StandardExternalFields.ID
OID = StandardExternalFields.OID
CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

INTERNAL_NTIID = StandardInternalFields.NTIID

CONTENT_NTIID = u'ContentNTIID'
LESSON_OVERVIEW_NTIID = u'LessonOverviewNTIID'

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstanceEnrollmentRecord)
@interface.implementer(IInternalObjectExternalizer)
class _CourseInstanceEnrollmentRecordExternalizer(object):

    def __init__(self, obj):
        self.obj = obj

    def toExternalObject(self, **unused_kwargs):
        result = LocatedExternalDict()
        result[MIMETYPE] = self.obj.mimeType
        result[CLASS] = "CourseInstanceEnrollmentRecord"
        # set fields
        result['Scope'] = self.obj.Scope
        principal = IPrincipal(self.obj.Principal, None)
        if principal is not None:
            result['Principal'] = principal.id
        entry = ICourseCatalogEntry(self.obj.CourseInstance, None)
        if entry is not None:
            result['Course'] = entry.ntiid
        return result


@component.adapter(ICourseOutlineNode)
@interface.implementer(IInternalObjectExternalizer)
class _CourseOutlineNodeExporter(object):

    def __init__(self, obj):
        self.node = obj

    def toExternalObject(self, **kwargs):
        mod_args = dict(**kwargs)
        mod_args['name'] = ''  # set default
        mod_args['decorate'] = False  # no decoration

        # use regular export
        result = to_external_object(self.node, **mod_args)
        if MIMETYPE not in result:
            decorateMimeType(self.node, result)
        if not getattr(self.node, LESSON_OVERVIEW_NTIID, None):
            result.pop(LESSON_OVERVIEW_NTIID, None)

        # make sure we provide an ntiid field
        if 'ntiid' not in result and getattr(self.node, 'ntiid', None):
            result['ntiid'] = self.node.ntiid

        # point to a valid .json source file
        name = result.get('src')
        if name:
            name = safe_filename(name)
            name = name + '.json' if not name.endswith('.json') else name
            result['src'] = name

        # set again to exporter and export children
        items = []
        mod_args['name'] = 'exporter'
        for node in self.node.values():
            ext_obj = to_external_object(node, **mod_args)
            items.append(ext_obj)
        if items:
            result[ITEMS] = items

        if ICourseOutline.providedBy(self.node):
            result.pop('publishBeginning', None)
            result.pop('publishEnding', None)
        else:
            result['isLocked'] = self.node.isLocked()
            result['isPublished'] = self.node.isPublished()
            result['isChildOrderLocked'] = self.node.isChildOrderLocked()

        # if content points to lesson pop both
        if      result.get(CONTENT_NTIID) \
            and result.get(LESSON_OVERVIEW_NTIID) == result.get(CONTENT_NTIID):
            result.pop(CONTENT_NTIID, None)
            result.pop(LESSON_OVERVIEW_NTIID, None)

        # don't leak internal OIDs
        for name in (NTIID, INTERNAL_NTIID, OID, LESSON_OVERVIEW_NTIID, CONTENT_NTIID):
            value = result.get(name)
            if      value \
                and is_valid_ntiid_string(value) \
                and is_ntiid_of_type(value, TYPE_OID):
                result.pop(name, None)

        return result


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IInternalObjectExternalizer)
class _CourseCatalogEntryExporter(object):

    REPLACE = (
        ('Video', 'video'), ('Title', 'title'), ('Preview', 'isPreview'),
        ('StartDate', 'startDate'), ('EndDate', 'endDate'),
        ('ProviderUniqueID', 'id'), ('ProviderDepartmentTitle', 'school'),
        ('AdditionalProperties', 'additionalProperties'),
        ('Credit', 'credit'), ('Instructors', 'instructors'),
        ('Description', 'description'), ('RichDescription', 'richDescription'),
        ('Schedule', 'schedule'), ('Duration', 'duration'),
        ('Prerequisites', 'prerequisites'),
        ('AdditionalProperties', 'additionalProperties'),
        ('awardable_credits', 'awardableCredits'),
    )

    REQUIRED = {x[0] for x in REPLACE} | {'tags', 'title', 'description'}

    INSTRUCTOR_REPLACE = (
        ('Name', 'name'), ('JobTitle', 'jobTitle'), ('Suffix', 'suffix'),
        ('Title', 'title'), ('Email', 'email'), ('Biography', 'biography'),
    )

    INSTRUCTOR_REQUIRED = {x[0] for x in INSTRUCTOR_REPLACE} | {'username', 'userid'}

    def __init__(self, obj):
        self.entry = obj

    def _remover(self, result, required=None):
        required = required or self.REQUIRED
        if isinstance(result, Mapping):
            for key in tuple(result.keys()):  # mutating
                if key not in required:
                    result.pop(key, None)

    def _replacer(self, result, frm, to):
        if isinstance(result, Mapping) and frm in result:
            result[to] = result.pop(frm, None)

    def _fix_instructors(self, instructors):
        for instructor in instructors or ():
            self._remover(instructor, self.INSTRUCTOR_REQUIRED)
            for frm, to in self.INSTRUCTOR_REPLACE:
                self._replacer(instructor, frm, to)

    def _fix_credits(self, data):
        for credit in data or ():
            self._remover(credit, ('Enrollment', 'Hours'))
            self._replacer(credit, 'Enrollment', 'enrollment')
            self._replacer(credit, 'Hours', 'hours')

    def toExternalObject(self, **kwargs):
        mod_args = dict(**kwargs)
        mod_args['name'] = ''  # set default
        mod_args['decorate'] = False  # no decoration
        result = to_external_object(self.entry, **mod_args)
        # remove unwanted keys
        self._remover(result)
        # replace keys
        for frm, to in self.REPLACE:
            self._replacer(result, frm, to)
        # credit
        self._fix_credits(result.get('credit'))
        # instructors
        self._fix_instructors(result.get('instructors'))
        # extra keys
        result['is_non_public'] = INonPublicCourseInstance.providedBy(self.entry)
        result['is_anonymously_but_not_publicly_accessible'] = IAnonymouslyAccessibleCourseInstance.providedBy(self.entry)
        return result


@component.adapter(ICourseInstanceVendorInfo)
@interface.implementer(IInternalObjectExternalizer)
class _CourseVendorInfoExporter(object):

    REMOVAL = (OID, CLASS, NTIID, CREATED_TIME, LAST_MODIFIED)

    def __init__(self, obj):
        self.obj = obj

    def _remover(self, result):
        if isinstance(result, Mapping):
            for key in tuple(result.keys()):  # mutating
                if key in self.REMOVAL:
                    result.pop(key, None)
        return result

    def toExternalObject(self, **kwargs):
        mod_args = dict(**kwargs)
        mod_args['name'] = ''  # set default
        mod_args['decorate'] = False  # no decoration
        result = to_external_object(self.obj, **mod_args)
        self._remover(result)
        return result


@component.adapter(ICourseInstanceSharingScope)
@interface.implementer(IInternalObjectExternalizer)
class _CourseInstanceSharingScopeExporter(object):

    def __init__(self, obj):
        self.entity = obj

    def toExternalObject(self, **unused_kwargs):
        result = LocatedExternalDict()
        clazz = getattr(self.entity, '__external_class_name__', None)
        if clazz:
            result[CLASS] = clazz
        else:
            result[CLASS] = self.entity.__class__.__name__
        decorateMimeType(self.entity, result)
        result['Username'] = self.entity.username
        if IUseNTIIDAsExternalUsername.providedBy(self.entity):
            result[ID] = self.entity.NTIID
        result['Scope'] = self.entity.__name__  # by definition
        course = find_interface(self.entity, ICourseInstance, strict=False)
        entry = ICourseCatalogEntry(course, None)
        result['Course'] = getattr(entry, 'ntiid', None)
        return result


@component.adapter(ICourseAdministrativeLevel)
@interface.implementer(IInternalObjectExternalizer)
class _AdminLevelExternalizer(object):

    def __init__(self, obj):
        self.obj = obj

    def toExternalObject(self, **unused_kwargs):
        result = LocatedExternalDict()
        result[MIMETYPE] = self.obj.mimeType
        result[CLASS] = "CourseAdministrativeLevel"
        result['Name'] = self.obj.__name__
        context_link = Link(self.obj)
        interface.alsoProvides(context_link, ILinkExternalHrefOnly)
        result['href'] = context_link
        items = list(self.obj)
        if items:
            result[ITEMS] = items
        return result


@component.adapter(ICourseTabPreferences)
@interface.implementer(IInternalObjectExternalizer)
class _CourseTabPreferencesExternalizer(InterfaceObjectIO):

    _ext_iface_upper_bound = ICourseTabPreferences

    def toExternalObject(self, *unused_args, **kwargs):  # pylint: disable=arguments-differ
        result = super(_CourseTabPreferencesExternalizer, self).toExternalObject(**kwargs)
        # pylint: disable=protected-access
        result['names'] = self._ext_self._names.data
        result['order'] = self._ext_self._order
        return result

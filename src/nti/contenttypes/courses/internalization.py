#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from datetime import timedelta
from collections import Mapping

import isodate

from zope import component
from zope import interface

from zope.interface.common.idatetime import IDateTime

from nti.base._compat import text_

from nti.common.string import is_true
from nti.common.string import is_false

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance

from nti.contenttypes.courses.legacy_catalog import ICourseCatalogLegacyEntry

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import IInternalObjectUpdater
from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseOutlineNode)
@interface.implementer(IInternalObjectUpdater)
class _CourseOutlineNodeUpdater(InterfaceObjectIO):

    _ext_iface_upper_bound = ICourseOutlineNode

    @property
    def node(self):
        return self._ext_self

    def set_ntiid(self, parsed):
        if 'ntiid' in parsed or NTIID in parsed:
            self.node.ntiid = parsed.get('ntiid') or parsed.get(NTIID)

    def set_locked(self, parsed):
        if not ICourseOutline.providedBy(self.node):
            locked = parsed.get('isLocked')
            if locked:
                self.node.lock(event=False)
            locked = parsed.get('isChildOrderLocked')
            if locked:
                self.node.childOrderLock(event=False)

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        self.set_ntiid(parsed)
        self.set_locked(parsed)
        isPublished = parsed.get('isPublished')  # capture param
        result = InterfaceObjectIO.updateFromExternalObject(self, parsed, *args, **kwargs)
        if ITEMS in parsed:
            for item in parsed.get(ITEMS) or ():
                # parse and update just in case
                if isinstance(item, Mapping):
                    factory = find_factory_for(item)
                    new_node = factory()
                    update_from_external_object(new_node, item, **kwargs)
                else:
                    new_node = item
                self.node.append(new_node)
        if      isPublished \
            and not ICourseOutline.providedBy(self.node) \
            and self.node.publishBeginning is None:
            self.node.publish(event=False)
        return result


def _quiet_delattr(o, k):
    try:
        delattr(o, k)
    except AttributeError:
        if k not in o.__dict__:
            return
        if hasattr(o, '_p_jar'):
            o._p_activate()
        o.__dict__.pop(k, None)
        if hasattr(o, '_p_jar'):
            o._p_changed = 1
    except TypeError:
        pass


def parse_duration(duration):
    splits = duration.split()
    if len(splits) >= 2:
        # We have durations as strings like "16 weeks"
        duration_number, duration_kind = duration.split()
        # Turn those into keywords for timedelta.
        normed = duration_kind.lower()
        return timedelta(**{normed: int(duration_number)})
    return isodate.parse_duration(duration)


def legacy_to_schema_transform(parsed, context=None, delete=False):
    for field, key in (('Term', 'term'),  # XXX: non-interface
                       ('ntiid', 'ntiid'),
                       ('Title', 'title'),
                       ('Description', 'description'),
                       ('ProviderUniqueID', 'id'),
                       ('RichDescription', 'richDescription'),
                       ('ProviderDepartmentTitle', 'school'),
                       ('InstructorsSignature', 'InstructorsSignature')):
        value = parsed.get(key)
        if value:
            parsed[text_(field)] = value
        elif delete:
            _quiet_delattr(context, field)

    if 'ntiid' in parsed and not parsed['ntiid']:
        parsed.pop('ntiid')

    for field, key in (('EndDate', 'endDate'),  # XXX: non-interface
                       ('StartDate', 'startDate')):
        value = parsed.get(key)
        if value:
            parsed[text_(field)] = IDateTime(value)
        elif delete:
            _quiet_delattr(context, field)

    if 'duration' in parsed:
        duration = parse_duration(parsed['duration'])
        parsed[u'Duration'] = duration
    elif delete and context is not None:
        context.Duration = None

    if 'isPreview' in parsed:
        parsed[u'Preview'] = parsed['isPreview'] or False
    elif 'Preview' not in parsed:
        parsed[u'Preview'] = getattr(context, 'Preview', '') or False

    if parsed.get('disable_calendar_overview', None) is not None:
        parsed[u'DisableOverviewCalendar'] = parsed['disable_calendar_overview']
    elif delete:
        parsed[u'DisableOverviewCalendar'] = False

    if parsed.get('video'):
        parsed[u'Video'] = parsed['video'].encode('utf-8')
    elif delete:
        _quiet_delattr(context, 'Video')

    for field, key, default in (('Schedule', 'schedule', {}),  # XXX: non-interface
                                ('Prerequisites', 'prerequisites', []),
                                ('AdditionalProperties', 'additionalProperties', None)):
        value = parsed.get(key, None)
        if value:
            parsed[text_(field)] = value or default
        elif delete:
            _quiet_delattr(context, field)

    if 'instructors' in parsed:
        instructors = []
        for inst in parsed['instructors'] or ():
            username = inst.get('username', u'')
            userid = inst.get('userid', u'')  # legacy
            instructors.append({
                MIMETYPE: 'application/vnd.nextthought.courses.coursecataloginstructorlegacyinfo',
                u'username': username,
                u'userid': userid,
                u'Name': inst.get('name'),
                u'JobTitle': inst.get('title'),
                u'defaultphoto': inst.get('defaultphoto'),
            })
        parsed[u'Instructors'] = instructors
    elif delete:
        _quiet_delattr(context, 'Instructors')

    if 'credit' in parsed:
        credit = []
        for data in parsed['credit'] or ():
            credit.append({
                MIMETYPE: 'application/vnd.nextthought.courses.coursecreditlegacyinfo',
                u'Hours': data.get('hours'),
                u'Enrollment': data.get('enrollment'),
            })
        parsed[u'Credit'] = credit
    elif delete:
        _quiet_delattr(context, 'Credit')

    return parsed


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IInternalObjectUpdater)
class _CourseCatalogEntryUpdater(InterfaceObjectIO):
    _ext_iface_upper_bound = ICourseCatalogEntry


@component.adapter(ICourseCatalogLegacyEntry)
class CourseCatalogLegacyEntryUpdater(_CourseCatalogEntryUpdater):

    _ext_iface_upper_bound = ICourseCatalogLegacyEntry

    def transform(self, parsed):
        legacy_to_schema_transform(parsed)
        return self

    def parseInstructors(self, parsed):
        instructors = parsed.get('Instructors')
        for idx, instructor in enumerate(instructors or ()):
            if not isinstance(instructor, Mapping):
                continue
            obj = find_factory_for(instructor)()
            instructors[idx] = update_from_external_object(obj, instructor)
        return self

    def parseCredit(self, parsed):
        credit = parsed.get('Credit')
        for idx, data in enumerate(credit or ()):
            if not isinstance(data, Mapping):
                continue
            obj = find_factory_for(data)()
            credit[idx] = update_from_external_object(obj, data)
        return self

    def parseMarkers(self, parsed):
        context = self._ext_replacement()
        is_non_public = parsed.get('is_non_public')
        if is_true(is_non_public):
            # This should move somewhere else...,
            # but for nti.app.products.courseware ACL support
            # (when these are not children of a course) it's convenient
            interface.alsoProvides(context, INonPublicCourseInstance)
        elif    is_false(is_non_public) \
            and INonPublicCourseInstance.providedBy(context):
            interface.noLongerProvides(context, INonPublicCourseInstance)

        is_anon = parsed.get('is_anonymously_but_not_publicly_accessible')
        if is_true(is_anon):
            interface.alsoProvides(context,
                                   IAnonymouslyAccessibleCourseInstance)
        elif    is_false(is_anon) \
            and IAnonymouslyAccessibleCourseInstance.providedBy(context):
            interface.noLongerProvides(context,
                                       IAnonymouslyAccessibleCourseInstance)
        return self

    def updateCourse(self):
        entry = self._ext_replacement()
        course = ICourseInstance(entry, None)
        if course is not None:  # update course interfaces
            if INonPublicCourseInstance.providedBy(entry):
                interface.alsoProvides(course, INonPublicCourseInstance)
            elif INonPublicCourseInstance.providedBy(course):
                interface.noLongerProvides(course,
                                           INonPublicCourseInstance)

            if IAnonymouslyAccessibleCourseInstance.providedBy(entry):
                interface.alsoProvides(course,
                                       IAnonymouslyAccessibleCourseInstance)
            elif IAnonymouslyAccessibleCourseInstance.providedBy(course):
                interface.noLongerProvides(course,
                                           IAnonymouslyAccessibleCourseInstance)
        return self

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        self.transform(parsed).parseInstructors(parsed).parseCredit(parsed)
        self.parseMarkers(parsed).updateCourse()
        return super(CourseCatalogLegacyEntryUpdater, self).updateFromExternalObject(parsed, *args, **kwargs)

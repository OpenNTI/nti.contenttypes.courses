#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.container.contained import Contained

from zope.i18n import translate

from zope.mimetype.interfaces import IContentTypeAware

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssignmentPolicies

from nti.contenttypes.courses.grading.interfaces import INullGrader
from nti.contenttypes.courses.grading.interfaces import IEqualGroupGrader
from nti.contenttypes.courses.grading.interfaces import ICategoryGradeScheme
from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.contenttypes.courses import MessageFactory as _

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dublincore.time_mixins import CreatedAndModifiedTimeMixin

from nti.externalization.representation import WithRepr

from nti.property.property import alias
from nti.property.property import CachedProperty

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.traversal.traversal import find_interface

from nti.zodb.persistentproperty import PersistentPropertyHolder


def get_assignment_policies(course):
    return IQAssignmentPolicies(course, None)


def get_assignment(ntiid):
    return component.queryUtility(IQAssignment, name=ntiid)


@interface.implementer(IContentTypeAware)
class BaseMixin(PersistentPropertyHolder, SchemaConfigured, Contained):

    parameters = {}  # IContentTypeAware

    def __init__(self, *args, **kwargs):
        # SchemaConfigured is not cooperative
        PersistentPropertyHolder.__init__(self)
        SchemaConfigured.__init__(self, *args, **kwargs)


@WithRepr
@interface.implementer(ICategoryGradeScheme)
class CategoryGradeScheme(BaseMixin):

    mime_type = mimeType = u'application/vnd.nextthought.courses.grading.categorygradescheme'

    createDirectFieldProperties(ICategoryGradeScheme)

    LatePenalty = 1

    weight = alias('Weight')
    penalty = alias('LatePenalty')
    dropLowest = alias('DropLowest')


@WithRepr
@interface.implementer(INullGrader)
class NullGrader(CreatedAndModifiedTimeMixin, BaseMixin):
    createDirectFieldProperties(INullGrader)

    mime_type = mimeType = u'application/vnd.nextthought.courses.grading.nullgrader'

    def validate(self):
        pass


@WithRepr
@interface.implementer(IEqualGroupGrader)
class EqualGroupGrader(CreatedAndModifiedTimeMixin, BaseMixin):
    createDirectFieldProperties(IEqualGroupGrader)

    mime_type = mimeType = u'application/vnd.nextthought.courses.grading.equalgroupgrader'

    groups = alias('Groups')

    def validate(self):
        if not self.groups:
            raise ValueError(_("Must specify at least a group"))

        count = 0
        for name, category in self.groups.items():
            weight = category.Weight
            if weight <= 0 or weight > 1:
                msg = translate(_("Invalid weight for category ${category}",
                                  mapping={'category': weight}))
                raise ValueError(msg)
            count += weight

        if round(count, 2) > 1.0:
            msg = _("Total category weight must be less than or equal to one")
            raise ValueError(msg)

        categories = self._raw_categories()
        for name in categories.keys():
            if name not in self.groups:
                msg = translate(_("${group} is an invalid group name",
                                  mapping={'group': name}))
                raise ValueError(msg)

        seen = set()
        for name in self.groups.keys():
            data = categories.get(name)
            if not data:
                msg = translate(_("No assignments are defined for category ${category}",
                                  mapping={'category': name}))
                raise ValueError(msg)

            for ntiid in [x['assignment'] for x in data]:
                if ntiid in seen:
                    msg = translate(_("Assignment ${asg} is in multiple groups",
                                      mapping={'asg': ntiid}))
                    raise ValueError(msg)
                seen.add(ntiid)
                assignment = get_assignment(ntiid)
                if assignment is None:
                    msg = translate(_("Assignment ${asg} does not exists",
                                      mapping={'asg': ntiid}))
                    raise ValueError(msg)

    @property
    def lastSynchronized(self):
        self_lastModified = self.lastModified or 0
        try:
            parent_lastSynchronized = self.course.lastSynchronized or 0
        except AttributeError:
            parent_lastSynchronized = 0
        return max(self_lastModified, parent_lastSynchronized)

    def _raw_categories(self):
        result = {}
        policies = get_assignment_policies(self.course)
        if policies is not None:
            for assignment in policies.assignments():
                policy = policies.getPolicyForAssignment(assignment)
                if not policy or policy.get('excluded', False):
                    continue

                auto_grade = policy.get('auto_grade') or {}
                grader = policy.get('grader') or auto_grade.get('grader')
                if not grader:
                    continue

                group = grader.get('group')
                if group:
                    data = dict()
                    total_points = auto_grade.get('total_points')
                    if total_points:
                        data['total_points'] = data['points'] = total_points
                    data.update(grader)  # override
                    data['assignment'] = assignment  # save

                    result.setdefault(group, [])
                    result[group].append(data)
        return result

    @CachedProperty('lastSynchronized')
    def _categories(self):
        return self._raw_categories()

    def _raw_rev_categories(self):
        result = {}
        for name, data in self._categories.items():
            for assignment in [x['assignment'] for x in data]:
                result[assignment] = name
        return result

    @CachedProperty('lastSynchronized')
    def _rev_categories(self):
        return self._raw_rev_categories()

    def _raw_assignments(self):
        return tuple(self._raw_rev_categories().keys())

    @CachedProperty('lastSynchronized')
    def _assignments(self):
        return self._raw_assignments()

    @property
    def course(self):
        return getattr(self.__parent__, 'course', None)

    def __len__(self):
        return len(self.groups)

    def __getitem__(self, key):
        return self.groups[key]

    def __iter__(self):
        return iter(self.groups)


@WithRepr
@interface.implementer(ICourseGradingPolicy)
class DefaultCourseGradingPolicy(CreatedAndModifiedTimeMixin, BaseMixin):
    createDirectFieldProperties(ICourseGradingPolicy)

    mime_type = mimeType = 'application/vnd.nextthought.courses.grading.defaultpolicy'

    creator = None
    grader = alias('Grader')

    def __setattr__(self, name, value):
        if name in ("Grader", "grader") and value is not None:
            value.__parent__ = self  # take ownership
        return BaseMixin.__setattr__(self, name, value)

    def validate(self):
        assert self.grader, "must specify a grader"
        self.grader.validate()

    def synchronize(self):
        course = self.course
        assert course, "must policy must be attached to a course"
        self.validate()

    @property
    def course(self):
        return find_interface(self, ICourseInstance, strict=False)

    def grade(self, *args, **kwargs):
        raise NotImplementedError()

    def updateLastMod(self, t=None):
        result = super(DefaultCourseGradingPolicy, self).updateLastMod(t)
        if self.grader is not None:
            self.grader.updateLastMod(t)
        return result

    def updateLastModIfGreater(self, t):
        result = super(DefaultCourseGradingPolicy, self).updateLastModIfGreater(t)
        if self.grader is not None:
            self.grader.updateLastModIfGreater(t)
        return result

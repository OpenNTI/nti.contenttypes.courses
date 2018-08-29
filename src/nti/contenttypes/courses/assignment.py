#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for assessments/assignment.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from collections import Mapping

from zope import component
from zope import interface

from zope.interface.common.mapping import IItemMapping
from zope.interface.common.mapping import IWriteMapping

from zope.annotation.factory import factory as an_factory

from zope.container.contained import Contained

from BTrees.OOBTree import OOBTree

from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IQAssessmentDateContext

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.interfaces import IInternalObjectExternalizer

from nti.externalization.persistence import NoPickle

MappingClass = OOBTree

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IQAssessmentDateContext)
class EmptyAssessmentDateContext(object):
    """
    Used when there is no context to adjust the dates.

    Not registered, but useful for testing.
    """

    def __init__(self, context=None):
        pass

    def assessments(self):
        return ()
    assignments = assessments  # BWC

    def of(self, asg):
        return asg

    def clear(self):
        pass

    def get(self, default=None, *unused_args, **unused_kwargs):
        return default

    def set(self, assessment, name, value):
        pass

    def size(self):
        return 0

    def __len__(self):
        return 0

    def __delitem__(self, key):
        raise KeyError(key)
EmptyAssignmentDateContext = EmptyAssessmentDateContext  # BWC


@NoPickle
class _Dates(object):

    def __init__(self, mapping, asg):
        self._asg = asg
        self._mapping = mapping

    def __getattr__(self, name):
        try:
            return self._mapping[self._asg.ntiid][name]
        except KeyError:
            return getattr(self._asg, name)


@interface.implementer(IItemMapping, IWriteMapping, IInternalObjectExternalizer)
class MappingAssessmentMixin(PersistentCreatedAndModifiedTimeObject, Contained):

    _SET_CREATED_MODTIME_ON_INIT = False

    def __init__(self):
        PersistentCreatedAndModifiedTimeObject.__init__(self)
        self._mapping = MappingClass()

    def assessments(self):
        return list(self._mapping.keys())
    assignments = assessments  # BWC

    def size(self):
        return len(self._mapping)

    def clear(self):
        size = self.size()
        for m in self._mapping.values():
            m.clear()
        self._mapping.clear()
        return size > 0

    def get_ntiid(self, assessment):
        return getattr(assessment, 'ntiid', assessment)

    def get(self, assessment, key, default=None):
        ntiid = self.get_ntiid(assessment)
        try:
            result = self[ntiid][key]
        except KeyError:
            result = default
        return result

    def set(self, assessment, name, value):
        ntiid = self.get_ntiid(assessment)
        data = self._mapping.get(ntiid)
        if data is None:
            data = self._mapping[ntiid] = MappingClass()
        data[name] = value

    def remove(self, assessment, name):
        ntiid = self.get_ntiid(assessment)
        data = self._mapping.get(ntiid)
        if data is not None:
            return data.pop(name, None)
        return None

    def __contains__(self, key):
        return key in self._mapping

    def __getitem__(self, key):
        return self._mapping[key]

    def __setitem__(self, key, value):
        self._mapping[key] = value

    def __delitem__(self, key):
        del self._mapping[key]

    def __len__(self):
        return self.size()

    def __conform__(self, iface):
        if ICourseInstance.isOrExtends(iface):
            return self.__parent__

    def toExternalObject(self, **kwargs):
        REMOVAL = StandardExternalFields.EXTERNAL_KEYS

        def _remover(result):
            if isinstance(result, Mapping):
                for key, value in tuple(result.items()):  # mutating
                    if key in REMOVAL:
                        result.pop(key, None)
                    else:
                        _remover(value)
            elif isinstance(result, (list, tuple, set)):
                for value in result:
                    _remover(value)
            return result
        result = to_external_object(self._mapping, **kwargs)
        return _remover(result)


@component.adapter(ICourseInstance)
@interface.implementer(IQAssessmentDateContext)
class MappingAssessmentDateContext(MappingAssessmentMixin):
    """
    A persistent mapping of assessment_ntiid -> {'available_for_submission_beginning': datetime}
    """

    def of(self, asg):
        if asg.ntiid in self._mapping:
            return _Dates(self._mapping, asg)
        return asg
MappingAssignmentDateContext = MappingAssessmentDateContext  # BWC

COURSE_INSTANCE_DATE_CONTEXT_KEY = 'nti.contenttypes.courses.assignment.MappingAssignmentDateContext'
COURSE_SUBINSTANCE_DATE_CONTEXT_KEY = COURSE_INSTANCE_DATE_CONTEXT_KEY  # BWC
CourseSubInstanceAssignmentDateContextFactory = an_factory(MappingAssignmentDateContext,
                                                           key=COURSE_INSTANCE_DATE_CONTEXT_KEY)


@component.adapter(ICourseInstance)
@interface.implementer(IQAssessmentPolicies)
class MappingAssessmentPolicies(MappingAssessmentMixin):
    """
    A persistent mapping of assessment ids to policy information,
    that is uninterpreted by this module.
    """

    def getPolicyForAssessment(self, key):
        return self._mapping.get(key, {})
    getPolicyForAssignment = getPolicyForAssessment  # BWC

    def __bool__(self):
        return bool(self._mapping)
    __nonzero__ = __bool__
MappingAssignmentPolicies = MappingAssessmentPolicies  # BWC

COURSE_DATE_CONTEXT_KEY = 'nti.contenttypes.courses.assignment.MappingAssignmentPolicies'
CourseInstanceAssignmentPoliciesFactory = an_factory(MappingAssignmentPolicies,
                                                     key=COURSE_DATE_CONTEXT_KEY)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.assessment.common import can_be_auto_graded

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IQAssessmentPolicyValidator

from nti.common.string import is_true
from nti.common.string import is_false

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.ntiids.ntiids import is_valid_ntiid_string


@interface.implementer(IQAssessmentPolicyValidator)
class DefaultAssessmentPolicyValidator(object):

    def question_points(self, auto_grade, ntiid):
        question_map = auto_grade.get('questions') or auto_grade
        points = question_map.get(ntiid) or question_map.get('default')
        return points

    def valid_auto_grade(self, policy, assignment, ntiid):
        if assignment is None:
            return
        auto_grade = policy.get('auto_grade')
        if not auto_grade:
            return
        total_points = auto_grade.get('total_points')
        if total_points is not None:
            try:
                assert int(total_points) >= 0
            except (AssertionError, TypeError, ValueError):
                msg = "Invalid total points in policy for %s (%s)"
                raise ValueError(msg % (ntiid, total_points))

        disable = auto_grade.get('disable')
        if disable is not None:
            if not (is_true(disable) or is_false(disable)):
                msg = "Invalid disable flag in policy for %s (%s)"
                raise ValueError(msg % (ntiid, total_points))
            elif is_true(disable):
                auto_grade['disable'] = True
            elif is_false(disable):
                auto_grade['disable'] = False

        if 'disable' not in auto_grade or not auto_grade['disable']:
            # Lot of legacy stuff has invalid auto_grade/total_points
            # combinations; so we'll warn for now.
            # If auto-gradable, make sure we can
            if not can_be_auto_graded(assignment):
                logger.warn('Assignment is not auto-gradable (%s)', 
                            ntiid)
            # We do allow total_points of zero, even though that
            # doesn't make sense (legacy content).
            if total_points is None:
                logger.warn('Auto-gradable assignment must have total_points (%s)',
                            ntiid)
        return auto_grade

    def validate_pointbased_policy(self, auto_grade, assignment, ntiid):
        if assignment is None:
            return
        name = auto_grade.get('name') if auto_grade else None
        if not name or (assignment and not IQAssignment.providedBy(assignment)):
            return
        if name.lower() in ('pointbased',):
            if assignment is None:
                raise AssertionError('Could not find assignment %s' % ntiid)
            for part in assignment.parts:
                for question in part.question_set.questions:
                    q_ntiid = question.ntiid
                    points = self.question_points(auto_grade, ntiid)
                    if not points or int(points) <= 0:
                        msg = "Invalid points in policy for question %s"
                        raise ValueError(msg % q_ntiid)
        else:
            logger.warn("Don't know how to validate policy %s in assignment %s",
                        name, ntiid)

    def validate(self, ntiid, policy):
        if not is_valid_ntiid_string(ntiid):
            return  # pragma no cover
        assignment = component.queryUtility(IQAssignment, name=ntiid)
        if assignment is None:
            logger.info("Could not find assessment (%s)", ntiid)
        auto_grade = self.valid_auto_grade(policy, assignment, ntiid)
        self.validate_pointbased_policy(auto_grade, assignment, ntiid)
DefaultAssignmentPolicyValidator = DefaultAssessmentPolicyValidator  # BWC


def validate_assigment_policies(course):
    course_policies = IQAssessmentPolicies(course, None)
    if not course_policies:
        return
    assessments = course_policies.assignments()
    policies = {
        a: course_policies.getPolicyForAssessment(a) for a in assessments
    }
    # let's try the course
    registry = component
    validator = IQAssessmentPolicyValidator(course, None)
    if validator is None:
        # Courses may be ISites
        try:
            names = ('',)
            registry = course.getSiteManager()
        except LookupError:
            entry = ICourseCatalogEntry(course, None)
            if entry:
                names = (entry.ntiid,)

        for name in names:
            try:
                validator = registry.getUtility(IQAssessmentPolicyValidator,
                                                name=name)
                break
            except LookupError:
                validator = None

    if validator is None:
        # let's try default validator
        validator = DefaultAssessmentPolicyValidator()
    # go through policies
    for k, v in policies.items():
        validator.validate(k, v)

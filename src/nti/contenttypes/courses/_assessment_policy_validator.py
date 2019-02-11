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

from nti.assessment.common import can_be_auto_graded

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IQAssessmentPolicyValidator
from nti.assessment.interfaces import AssessmentPolicyValidationError

from nti.common.string import is_true
from nti.common.string import is_false

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


def check_assessment(ntiid, warning=True, provided=IQAssignment):
    result = component.queryUtility(IQAssignment, name=ntiid)
    if not provided.providedBy(result):
        if warning:
            logger.warn("Could not find assessment (%s)", ntiid)
        else:
            raise AssessmentPolicyValidationError("Cannot find assessment %s", ntiid)
    return result


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
                raise AssessmentPolicyValidationError(msg % (ntiid, total_points))

        disable = auto_grade.get('disable')
        if disable is not None:
            if not (is_true(disable) or is_false(disable)):
                msg = "Invalid disable flag in policy for %s"
                raise AssessmentPolicyValidationError(msg % (ntiid,))
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
                raise AssessmentPolicyValidationError('Could not find assignment %s' % ntiid)
            for part in assignment.parts:
                for question in part.question_set.questions:
                    q_ntiid = question.ntiid
                    points = self.question_points(auto_grade, ntiid)
                    if not points or int(points) <= 0:
                        msg = "Invalid points in policy for question %s"
                        raise AssessmentPolicyValidationError(msg % q_ntiid)
        else:
            logger.warn("Don't know how to validate policy %s in assignment %s",
                        name, ntiid)

    def validate_submissions(self, auto_grade, policy, assignment, ntiid):
        if assignment is None:
            return

        max_submissions = policy.get('max_submissions')
        if max_submissions is not None:
            try:
                max_submissions = int(max_submissions)
                # -1 is unlimited
                assert max_submissions == -1 or max_submissions >= 0
            except (AssertionError, TypeError, ValueError):
                msg = "Invalid max_submissions in policy for %s (%s)"
                raise AssessmentPolicyValidationError(msg % (ntiid, max_submissions))

        if not max_submissions or max_submissions == 1:
            # No need to validate anything else
            return

        submission_priority = policy.get('submission_priority')
        if submission_priority:
            submission_priority = submission_priority.lower()
            if submission_priority not in ('most_recent', 'highest_grade'):
                msg = "Invalid submission_priority in policy for %s (%s)"
                raise AssessmentPolicyValidationError(msg % (ntiid, submission_priority))

            if      submission_priority == 'highest_grade' \
                and (   auto_grade is None \
                     or ('disable' in auto_grade and auto_grade['disable'])):
                # Cannot take the highest graded submission without autograde
                # XXX: Is this correct?
                msg = "Invalid submission_priority for non auto-graded policy for %s (%s)"
                raise AssessmentPolicyValidationError(msg % (ntiid, submission_priority))
        else:
            # Default to 'most_recent'; we could do something based on
            # auto-grade here too.
            policy['submission_priority'] = 'most_recent'

    def validate_completion(self, unused_auto_grade, policy, assignment, ntiid):
        if assignment is None:
            return

        passing_perc = policy.get('completion_passing_percent')
        if passing_perc is not None:
            try:
                passing_perc = float(passing_perc)
                assert passing_perc >= 0
                assert passing_perc <= 1
            except (AssertionError, TypeError, ValueError):
                msg = "Invalid completion_passing_percent in policy for %s (%s)"
                raise AssessmentPolicyValidationError(msg % (ntiid, passing_perc))

    def validate(self, ntiid, policy):
        if not is_valid_ntiid_string(ntiid):
            return  # pragma no cover
        assignment = check_assessment(ntiid)
        auto_grade = self.valid_auto_grade(policy, assignment, ntiid)
        self.validate_pointbased_policy(auto_grade, assignment, ntiid)
        self.validate_submissions(auto_grade, policy, assignment, ntiid)
        self.validate_completion(auto_grade, policy, assignment, ntiid)
DefaultAssignmentPolicyValidator = DefaultAssessmentPolicyValidator  # BWC


def validate_assigment_policies(context, check_exists=False):
    if not IQAssessmentPolicies.providedBy(context):
        course = ICourseInstance(context, None)
        course_policies = IQAssessmentPolicies(course, None)
    else:
        course_policies = context
        course = find_interface(context, ICourseInstance, strict=False)
    if not course_policies:
        return
    assessments = course_policies.assignments()
    policies = {
        a: course_policies.getPolicyForAssessment(a) for a in assessments or ()
    }
    validator = IQAssessmentPolicyValidator(course, None)
    if validator is None:
        # let's try default validator
        validator = DefaultAssessmentPolicyValidator()
    # go through policies
    for ntiid, v in policies.items():
        if check_exists:
            check_assessment(ntiid, False)
        validator.validate(ntiid, v)

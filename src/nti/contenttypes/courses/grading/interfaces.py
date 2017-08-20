#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Course-related grading interfaces.

.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.location.interfaces import IContained

from nti.base.interfaces import ICreated
from nti.base.interfaces import ILastModified

from nti.schema.field import Dict
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import ValidTextLine


class IGrader(IContained, ILastModified):
    """
    Marker interface for a grader
    """

    def validate():
        """
        validate this grader
        """


class INullGrader(IGrader):
    """
    A grader that does nothing
    """


class ICategoryGradeScheme(interface.Interface):

    Weight = Number(title=u"Category weight",
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    required=True)

    LatePenalty = Number(title=u"Late penalty",
                         default=1,
                         min=0.0,
                         max=1.0,
                         required=False)


class IEqualGroupGrader(IGrader):

    Groups = Dict(key_type=ValidTextLine(title=u"Category Name"),
                  value_type=Object(ICategoryGradeScheme,
                                    title=u"Category grade scheme",
                                    required=True),
                  min_length=1)


class ICourseGradingPolicy(IContained, ILastModified, ICreated):
    """
    A marker interface to store a course grading policy
    """

    Grader = Object(IGrader, required=True, title=u"Grader")

    def validate():
        """
        validate this policy
        """

    def synchronize():
        """
        Perform any adjustment of this policy during course synchronization
        """

    def grade(principal):
        """
        Returns an :class:`IPredictedGrade` or None if no valid grade
        could be produced.
        """


class IPredictedGrade(interface.Interface):
    """
    A predicted grade for a student in a course. This is not
    related to IGrade.
    """

    Grade = ValidTextLine(title=u"The student's grade according to the current grade scheme",
                          description=u"A grade useful for display purposes.""")

    RawValue = Number(title=u"The raw value of the grade",
                      description=u"""Represents the fraction of PointsEarned to
                                  PointsAvailable.""")

    Correctness = Number(title=u"The correctness value of the grade, 100 * RawValue",
                         description=u"""This is RawValue * 100, e.g. the percentage
                                     representation of raw value.""")

    DisplayableGrade = ValidTextLine(
        title=u"A formatted description of the grade",
        description=u"Should default to the same value as Correctness unless a grading scheme is set")

    PointsEarned = Number(title=u"The number of points earned at this point in the course",
                          required=False)

    PointsAvailable = Number(title=u"The number of available points at this point in the course",
                             required=False)

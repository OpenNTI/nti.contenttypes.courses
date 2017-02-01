#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Course-related grading interfaces.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.container.interfaces import IContained

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
    Weight = Number(title="Category weight",
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    required=True)

    LatePenalty = Number(title="Late penalty",
                         default=1,
                         min=0.0,
                         max=1.0,
                         required=False)


class IEqualGroupGrader(IGrader):

    Groups = Dict(key_type=ValidTextLine(title="Category Name"),
                  value_type=Object(ICategoryGradeScheme,
                                    title="Category grade scheme",
                                    required=True),
                  min_length=1)


class ICourseGradingPolicy(IContained, ILastModified, ICreated):
    """
    A marker interface to store a course grading policy
    """

    Grader = Object(IGrader, required=True, title="Grader")

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
        return the [current] grade for the specified user/principal. May
        return None if no valid grade could be produced.
        """
        
class IPredictedGrade(interface.Interface):
    """
    A predicted grade for a student in a course. This is not
    related to IGrade. 
    """
        
    Grade = ValidTextLine(title="The student's grade according to the current grade scheme")
    RawValue = Number(title="The raw value of the grade")
    Correctness = Number(title="The correctness value of the grade")
    PointsEarned = Number(title="The number of points earned at this point in the course",
                          required=False)
    PointsAvailable = Number(title="The number of available points at this point in the course",
                             required=False)

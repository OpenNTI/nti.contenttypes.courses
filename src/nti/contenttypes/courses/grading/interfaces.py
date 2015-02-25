#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Course-related grading interfaces.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.container.interfaces import IContained

from nti.dublincore.interfaces import ILastModified

from nti.schema.field import Dict
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import ValidTextLine
	
class IGrader(IContained):
	"""
	Marker interface for a grader
	"""
	
	def validate():
		"""
		validate this grader
		"""

class IEqualGroupGrader(IGrader):

	Groups = Dict(key_type=ValidTextLine(title="Category Name"),
	  			  value_type=Number(title="Category Percentage"),
				  min_length=1)


class ICourseGradingPolicy(IContained, ILastModified):
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
		return the [current] grade for the specified user/principal
		"""

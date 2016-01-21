#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NTIID support for course-related objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseOutlineNode

from nti.ntiids.interfaces import INTIIDResolver

@interface.implementer(INTIIDResolver)
class _CourseInfoNTIIDResolver(object):
	"""
	Resolves course info ntiids through the catalog.
	"""

	def resolve(self, ntiid):
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is not None:
			try:
				return catalog.getCatalogEntry(ntiid)
			except KeyError:
				pass
		return None

@interface.implementer(INTIIDResolver)
class _CourseOutlineNodeNTIIDResolver(object):
	"""
	Resolves outline nodes
	"""

	def resolve(self, ntiid):
		result = component.queryUtility(ICourseOutlineNode, name=ntiid)
		return result

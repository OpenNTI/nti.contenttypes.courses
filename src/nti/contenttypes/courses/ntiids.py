#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NTIID support for course-related objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from nti.ntiids.interfaces import INTIIDResolver

from .interfaces import ICourseCatalog

@interface.implementer(INTIIDResolver)
class _CourseInfoNTIIDResolver(object):
	"""
	Resolves course info ntiids through the catalog.
	"""

	def resolve(self, ntiid):
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is None:
			return
		try:
			return catalog.getCatalogEntry(ntiid)
		except KeyError:
			return None

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

from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSectionImporter

@interface.implementer(ICourseImporter)
class CourseImporter(object):

	def process(self, context, filer):
		course = ICourseInstance(context)
		for name, importer in sorted(component.getUtilitiesFor(ICourseSectionImporter)):
			logger.info("Processing %s", name)
			importer.process(course, filer)

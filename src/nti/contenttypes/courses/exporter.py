#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from StringIO import StringIO

import simplejson

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import ICourseExporter 
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.externalization import to_external_object

@interface.implementer(ICourseSectionExporter)
class CourseOutlineExporer(object):

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = "Sections/%s" % course.__name__
		else:
			bucket = None
		# export to json
		source = StringIO()
		ext_obj = to_external_object(course.Outline, name='exporter', decorate=False)
		simplejson.dump(ext_obj, source, indent=4)
		source.seek(0)
		# save in filer
		filer.save("outline.json", source, contentType="text/json", 
				   bucket=bucket, overwrite=True)
		# save outlines for subinstances
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				self.export(sub_instance, filer)

@interface.implementer(ICourseExporter)
class CourseExporter(object):
	
	def export(self, context, filer):
		course = ICourseInstance(context)
		for _, exporter in list(component.getUtilitiesFor(ICourseSectionExporter)):
			exporter.export(course, filer)

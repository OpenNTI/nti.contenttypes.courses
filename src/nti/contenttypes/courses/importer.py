#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time
import simplejson

from zope import component
from zope import interface

from zope.event import notify

from nti.contenttypes.courses._role_parser import fill_roles_from_json

from nti.contenttypes.courses.interfaces import SECTIONS

from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.contenttypes.courses.interfaces import CourseRolesSynchronized
from nti.contenttypes.courses.interfaces import CourseVendorInfoSynchronized

from nti.contenttypes.courses.utils import clear_course_outline
from nti.contenttypes.courses.utils import get_course_vendor_info
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.internalization import update_from_external_object

@interface.implementer(ICourseSectionImporter)
class BaseSectionImporter(object):

	def load(self, source):
		if hasattr(source, "read"):
			result = simplejson.load(source)
		elif hasattr(source, "readContents"):
			data = source.readContents()
			result = simplejson.loads(data)
		elif hasattr(source, "data"):
			result = simplejson.loads(source.data)
		else:
			result = simplejson.loads(source)
		return result

@interface.implementer(ICourseSectionImporter)
class CourseOutlineExporter(BaseSectionImporter):

	def process(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s/" % (SECTIONS, course.__name__)
		else:
			bucket = u''
		path = bucket + 'course_outline.json'
		source = filer.get(path)
		if source is not None:
			ext_obj = self.load(source)
			clear_course_outline(course.Outline) # not merging
			update_from_external_object(course.Outline, ext_obj, notify=False)
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class VendorInfoImporter(BaseSectionImporter):

	def process(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s/" % (SECTIONS, course.__name__)
		else:
			bucket = u''
		path = bucket + 'vendor_info.json'
		source = filer.get(path)
		if source is not None:
			verdor_info = get_course_vendor_info(course, True)
			verdor_info.clear()  # not merging
			verdor_info.update(self.load(source))
			verdor_info.lastModified = time.time()
			notify(CourseVendorInfoSynchronized(course))
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseSectionImporter)
class RoleInfoImporter(BaseSectionImporter):

	def process(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s/" % (SECTIONS, course.__name__)
		else:
			bucket = u''
		path = bucket + 'role_info.json'
		source = filer.get(path)
		if source is not None:
			source = self.load(source)
			fill_roles_from_json(course, source)
			notify(CourseRolesSynchronized(course))
		for sub_instance in get_course_subinstances(course):
			self.process(sub_instance, filer)

@interface.implementer(ICourseImporter)
class CourseImporter(object):

	def process(self, context, filer):
		course = ICourseInstance(context)
		for name, importer in sorted(component.getUtilitiesFor(ICourseSectionImporter)):
			logger.info("Processing %s", name)
			importer.process(course, filer)

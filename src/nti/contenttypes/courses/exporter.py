#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from StringIO import StringIO

from xml.dom import minidom

import simplejson

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import SECTIONS, ICourseCatalogEntry

from nti.contenttypes.courses.interfaces import ICourseExporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_vendor_info
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.externalization import to_external_object

@interface.implementer(ICourseSectionExporter)
class CourseOutlineExporter(object):

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s" % (SECTIONS, course.__name__)
		else:
			bucket = None
		# export to json
		source = StringIO()
		ext_obj = to_external_object(course.Outline, name='exporter', decorate=False)
		simplejson.dump(ext_obj, source, indent=4)
		source.seek(0)
		# save in filer
		filer.save("outline.json", source, contentType="application/json",
				   bucket=bucket, overwrite=True)
		# save outlines for subinstances
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class VendorInfoExporter(object):

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s" % (SECTIONS, course.__name__)
		else:
			bucket = None
		verdor_info = get_course_vendor_info(course, False)
		if verdor_info:
			# export to json
			source = StringIO()
			ext_obj = to_external_object(verdor_info, decorate=False)
			simplejson.dump(ext_obj, source, indent=4)
			source.seek(0)
			# save in filer
			filer.save("vendor_info.json", source, contentType="application/json",
					   bucket=bucket, overwrite=True)
			# save outlines for subinstances
			for sub_instance in get_course_subinstances(course):
				if sub_instance.Outline is not course.Outline:
					self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class BundleMetaInfoExporter(object):

	def export(self, context, filer):
		course = ICourseInstance(context)
		course = get_parent_course(course)
		entry = ICourseCatalogEntry(course)
		data = {u'ntiid':u'',
				u'title': entry.Title,
				u"ContentPackages": [x.ntiid for x in get_course_packages(course)]}
		source = StringIO()
		ext_obj = to_external_object(data, decorate=False)
		simplejson.dump(ext_obj, source, indent=4)
		source.seek(0)
		# save in filer
		filer.save("bundle_meta_info.json", source,
					contentType="application/json", overwrite=True)

@interface.implementer(ICourseSectionExporter)
class BundleDCMetadataExporter(object):

	def export(self, context, filer):
		course = ICourseInstance(context)
		course = get_parent_course(course)
		entry = ICourseCatalogEntry(course)

		DOMimpl = minidom.getDOMImplementation()
		xmldoc = DOMimpl.createDocument(None, "metadata", None)
		doc_root = xmldoc.documentElement
		doc_root.setAttributeNS(None, "xmlns:dc", "http://purl.org/dc/elements/1.1/")

		for creator in entry.creators or ():
			node = xmldoc.createElement("dc:creator")
			node.appendChild(xmldoc.createTextNode(creator))
			doc_root.appendChild(node)

		node = xmldoc.createElement("dc:title")
		node.appendChild(xmldoc.createTextNode(entry.Title))
		doc_root.appendChild(node)

		source = xmldoc.toprettyxml(encoding="UTF-8")
		for name in ("dc_metadata.xml", "bundle_dc_metadata.xml"):
			filer.save(name, source, contentType="application/xml", overwrite=True)

@interface.implementer(ICourseExporter)
class CourseExporter(object):

	def export(self, context, filer):
		course = ICourseInstance(context)
		for _, exporter in list(component.getUtilitiesFor(ICourseSectionExporter)):
			exporter.export(course, filer)

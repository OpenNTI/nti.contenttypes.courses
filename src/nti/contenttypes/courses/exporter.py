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

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.assessment.interfaces import IQAssessmentPolicies

from nti.common import mimetypes

from nti.contentlibrary.interfaces import IDelimitedHierarchyKey
from nti.contentlibrary.interfaces import IEnumerableDelimitedHierarchyBucket

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import SECTIONS
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.interfaces import ICourseExporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_vendor_info
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import IInternalObjectExternalizer

@interface.implementer(ICourseSectionExporter)
class BaseSectionExporter(object):
	
	def dump(self, ext_obj):
		source = StringIO()
		simplejson.dump(ext_obj, source, indent='\t', sort_keys=True)
		source.seek(0)
		return source

@interface.implementer(ICourseSectionExporter)
class CourseOutlineExporter(BaseSectionExporter):

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s" % (SECTIONS, course.__name__)
		else:
			bucket = None
		ext_obj = to_external_object(course.Outline, name='exporter', decorate=False)
		source = self.dump(ext_obj)
		filer.save("course_outline.json", source, contentType="application/json",
				   bucket=bucket, overwrite=True)
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class VendorInfoExporter(BaseSectionExporter):

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s" % (SECTIONS, course.__name__)
		else:
			bucket = None
		verdor_info = get_course_vendor_info(course, False)
		if verdor_info:
			ext_obj = to_external_object(verdor_info, name="exporter", decorate=False)
			source = self.dump(ext_obj)
			filer.save("vendor_info.json", source, contentType="application/json",
					   bucket=bucket, overwrite=True)
		for sub_instance in get_course_subinstances(course):
			self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class BundleMetaInfoExporter(BaseSectionExporter):

	def export(self, context, filer):
		course = ICourseInstance(context)
		course = get_parent_course(course)
		entry = ICourseCatalogEntry(course)
		data = {u'ntiid':u'',
				u'title': entry.Title,
				u"ContentPackages": [x.ntiid for x in get_course_packages(course)]}
		ext_obj = to_external_object(data, decorate=False)
		source = self.dump(ext_obj)
		filer.save("bundle_meta_info.json", source,
					contentType="application/json", overwrite=True)

@interface.implementer(ICourseSectionExporter)
class BundleDCMetadataExporter(BaseSectionExporter):

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

@interface.implementer(ICourseSectionExporter)
class BundlePresentationAssetsExporter(BaseSectionExporter):

	__PA__ = 'presentation-assets'

	def _get_path(self, current):
		result = []
		while True:
			try:
				result.append(current.__name__)
				if current.__name__ == self.__PA__:
					break
				current = current.__parent__
			except AttributeError:
				break
		result.reverse()
		return '/'.join(result)

	def _process_root(self, root, bucket, filer):
		if IEnumerableDelimitedHierarchyBucket.providedBy(root):
			root_path = self._get_path(root)
			for child in root.enumerateChildren():
				if IDelimitedHierarchyKey.providedBy(child):
					name = child.__name__
					source = child.readContents()
					bucket_path = bucket + root_path
					contentType = mimetypes.guess_type(name) or u'application/octet-stream'
					filer.save(name, source, bucket=bucket_path,
							   contentType=contentType, overwrite=True)
				elif IEnumerableDelimitedHierarchyBucket.providedBy(child):
					self._process_root(child, bucket, filer)

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = u'%s/%s/' % (SECTIONS, course.__name__)
		else:
			bucket = u''
		for resource in course.PlatformPresentationResources or ():
			self._process_root(resource.root, bucket, filer)

@interface.implementer(ICourseSectionExporter)
class RoleInfoExporter(BaseSectionExporter):

	def _role_export_map(self, course):
		result = {}
		roles = IPrincipalRoleMap(course)
		for name in (RID_TA, RID_INSTRUCTOR, RID_CONTENT_EDITOR):
			deny = []
			allow = []
			for principal, setting in roles.getPrincipalsForRole(name) or ():
				pid = getattr(principal, 'id', str(principal))
				if setting == Allow:
					allow.append(pid)
				else:
					deny.append(pid)
			if allow or deny:
				role_data = result[name] = {}
				for name, users in (('allow', allow), ('deny', deny)):
					if users:
						role_data[name] = users
		return result

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = u'%s/%s/' % (SECTIONS, course.__name__)
		else:
			bucket = None
		result = self._role_export_map(course)
		source = self.dump(result)
		filer.save("role_info.json", source, bucket=bucket,
					contentType="application/json", overwrite=True)
		for sub_instance in get_course_subinstances(course):
			self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class AssignmentPoliciesExporter(BaseSectionExporter):

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = u'%s/%s/' % (SECTIONS, course.__name__)
		else:
			bucket = None
		policies = IQAssessmentPolicies(course)
		if policies and IInternalObjectExternalizer.providedBy(policies):
			result = policies.toExternalObject()
			source = self.dump(result)
			filer.save("assignment_policies.json", source, bucket=bucket,
						contentType="application/json", overwrite=True)
		for sub_instance in get_course_subinstances(course):
			self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class CourseInfoExporter(BaseSectionExporter):

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = u'%s/%s/' % (SECTIONS, course.__name__)
		else:
			bucket = None
		entry = ICourseCatalogEntry(course)
		ext_obj = to_external_object(entry, name="exporter", decorate=False)
		source = self.dump(ext_obj)
		filer.save("course_info.json", source, bucket=bucket,
					contentType="application/json", overwrite=True)
		for sub_instance in get_course_subinstances(course):
			self.export(sub_instance, filer)

@interface.implementer(ICourseExporter)
class CourseExporter(object):

	def export(self, context, filer):
		course = ICourseInstance(context)
		for name, exporter in sorted(component.getUtilitiesFor(ICourseSectionExporter)):
			logger.info("Processing %s", name)
			exporter.export(course, filer)

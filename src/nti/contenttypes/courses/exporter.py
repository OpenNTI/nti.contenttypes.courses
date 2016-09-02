#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time
from io import StringIO

from xml.dom import minidom

import simplejson

from zope import component
from zope import interface

from zope.event import notify

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IQAssessmentDateContext

from nti.common import mimetypes

from nti.contentlibrary.bundle import BUNDLE_META_NAME

from nti.contentlibrary.dublincore import DCMETA_FILENAME

from nti.contentlibrary.interfaces import IDelimitedHierarchyKey
from nti.contentlibrary.interfaces import IEnumerableDelimitedHierarchyBucket

from nti.contenttypes.courses import ROLE_INFO_NAME
from nti.contenttypes.courses import VENDOR_INFO_NAME
from nti.contenttypes.courses import CATALOG_INFO_NAME
from nti.contenttypes.courses import COURSE_OUTLINE_NAME
from nti.contenttypes.courses import ASSIGNMENT_POLICIES_NAME

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import SECTIONS
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseExporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSectionExporter
from nti.contenttypes.courses.interfaces import ICourseOutlineCalendarNode

from nti.contenttypes.courses.interfaces import CourseInstanceExportedEvent

from nti.contenttypes.courses.utils import get_course_vendor_info
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import make_ntiid

@interface.implementer(ICourseSectionExporter)
class BaseSectionExporter(object):

	def dump(self, ext_obj):
		source = StringIO()
		simplejson.dump(ext_obj, source, indent='\t', sort_keys=True)
		source.seek(0)
		return source

	def course_bucket(self, course):
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s" % (SECTIONS, course.__name__)
		else:
			bucket = None
		return bucket

@interface.implementer(ICourseSectionExporter)
class CourseOutlineExporter(BaseSectionExporter):

	def asXML(self, outline, course=None):
		DOMimpl = minidom.getDOMImplementation()
		xmldoc = DOMimpl.createDocument(None, "course", None)
		doc_root = xmldoc.documentElement

		# process main course elemet
		entry = ICourseCatalogEntry(course, None)
		if entry is not None:
			ntiid = make_ntiid(nttype="NTICourse", base=entry.ntiid)
			doc_root.setAttribute("ntiid", ntiid)
			doc_root.setAttribute("label", entry.title or u'')
			doc_root.setAttribute("courseName", entry.ProviderUniqueID or u'')

		packages = get_course_packages(course)
		if packages:
			doc_root.setAttribute("courseInfo", packages[0].ntiid)

		node = xmldoc.createElement("info")
		node.setAttribute("src", "course_info.json")
		doc_root.appendChild(node)

		# process units and lessons
		def _recur(node, xml_parent, level=-1):
			if ICourseOutlineCalendarNode.providedBy(node):
				xml_node = xmldoc.createElement("lesson")
				if node.src:
					xml_node.setAttribute("src", node.src)
					xml_node.setAttribute("isOutlineStubOnly", "false")
				else:
					xml_node.setAttribute("isOutlineStubOnly", "true")
				if node.ContentNTIID != node.LessonOverviewNTIID:
					xml_node.setAttribute("topic-ntiid", node.ContentNTIID)

				if node.AvailableBeginning or node.AvailableEnding:
					dates = []
					for data in (node.AvailableBeginning, node.AvailableEnding):
						dates.append(to_external_object(data) if data else u"")
					value = ",".join(dates)
					xml_node.setAttribute("date", value)
			elif not ICourseOutline.providedBy(node):
				xml_node = xmldoc.createElement("unit")
				ntiid = make_ntiid(nttype="NTICourseUnit", base=node.ntiid)
				xml_node.setAttribute("ntiid", ntiid)
			else:
				xml_node = None
			if xml_node is not None:
				title = getattr(node, 'title', None) or u''
				xml_node.setAttribute("label", title)
				xml_node.setAttribute("title", title)
				xml_node.setAttribute("levelnum", str(level))
				xml_parent.appendChild(xml_node)
			else:
				xml_node = xml_parent

			# process children
			for child in node.values():
				_recur(child, xml_node, level + 1)
		_recur(outline, doc_root)

		result = xmldoc.toprettyxml(encoding="UTF-8")
		return result

	def export(self, context, filer):
		course = ICourseInstance(context)
		bucket = self.course_bucket(course)

		# as json
		ext_obj = to_external_object(course.Outline, name='exporter', decorate=False)
		source = self.dump(ext_obj)
		filer.save(COURSE_OUTLINE_NAME, source, contentType="application/json",
				   bucket=bucket, overwrite=True)

		# as xml
		source = self.asXML(course.Outline, course)
		filer.save("course_outline.xml", source, contentType="application/xml",
					bucket=bucket, overwrite=True)

		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class VendorInfoExporter(BaseSectionExporter):

	def export(self, context, filer):
		course = ICourseInstance(context)
		bucket = self.course_bucket(course)
		verdor_info = get_course_vendor_info(course, False)
		if verdor_info:
			ext_obj = to_external_object(verdor_info, name="exporter", decorate=False)
			source = self.dump(ext_obj)
			filer.save(VENDOR_INFO_NAME, source, contentType="application/json",
					   bucket=bucket, overwrite=True)
		for sub_instance in get_course_subinstances(course):
			self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class BundleMetaInfoExporter(BaseSectionExporter):

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			return
		entry = ICourseCatalogEntry(course)
		data = {u'ntiid':u'',
				u'title': entry.Title,
				u"ContentPackages": [x.ntiid for x in get_course_packages(course)]}
		ext_obj = to_external_object(data, decorate=False)
		source = self.dump(ext_obj)
		filer.save(BUNDLE_META_NAME, source,
				   contentType="application/json", overwrite=True)

@interface.implementer(ICourseSectionExporter)
class BundleDCMetadataExporter(BaseSectionExporter):

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			return
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
		for name in (DCMETA_FILENAME, "bundle_dc_metadata.xml"):
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
		bucket = self.course_bucket(course)
		bucket = u'' if not bucket else bucket + '/'
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
		bucket = self.course_bucket(course)
		result = self._role_export_map(course)
		source = self.dump(result)
		filer.save(ROLE_INFO_NAME, source, bucket=bucket,
				   contentType="application/json", overwrite=True)
		for sub_instance in get_course_subinstances(course):
			self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class AssignmentPoliciesExporter(BaseSectionExporter):

	def _process(self, course):
		policies = IQAssessmentPolicies(course)
		result = to_external_object(policies, decorate=False)
		date_context = IQAssessmentDateContext(course)
		date_context = to_external_object(date_context, decorate=False)
		for key, value in date_context.items():
			entry = result.get(key)
			if entry is not None:
				entry.update(value)
			else:
				result[key] = entry
		return result

	def export(self, context, filer):
		course = ICourseInstance(context)
		bucket = self.course_bucket(course)
		result = self._process(course)
		if result:
			source = self.dump(result)
			filer.save(ASSIGNMENT_POLICIES_NAME, source, bucket=bucket,
					   contentType="application/json", overwrite=True)
		for sub_instance in get_course_subinstances(course):
			self.export(sub_instance, filer)

@interface.implementer(ICourseSectionExporter)
class CourseInfoExporter(BaseSectionExporter):

	def export(self, context, filer):
		course = ICourseInstance(context)
		bucket = self.course_bucket(course)
		entry = ICourseCatalogEntry(course)
		ext_obj = to_external_object(entry, name="exporter", decorate=False)
		source = self.dump(ext_obj)
		filer.save(CATALOG_INFO_NAME, source, bucket=bucket,
				   contentType="application/json", overwrite=True)
		for sub_instance in get_course_subinstances(course):
			self.export(sub_instance, filer)

@interface.implementer(ICourseExporter)
class CourseExporter(object):

	def export(self, context, filer):
		now = time.time()
		course = ICourseInstance(context)
		entry = ICourseCatalogEntry(course)
		for name, exporter in sorted(component.getUtilitiesFor(ICourseSectionExporter)):
			logger.info("Processing %s", name)
			exporter.export(course, filer)
		notify(CourseInstanceExportedEvent(course))
		for subinstance in get_course_subinstances(course):
			notify(CourseInstanceExportedEvent(subinstance))
		logger.info("Course %s exported in %s(s)", entry.ntiid, time.time() - now)

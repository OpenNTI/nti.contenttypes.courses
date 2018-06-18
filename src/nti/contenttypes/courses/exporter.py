#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import six
import time
import mimetypes
from numbers import Number
from datetime import datetime
from collections import Mapping
from collections import Iterable

from six.moves import cStringIO

from xml.dom import minidom

import simplejson

from zope import component
from zope import interface

from zope.event import notify

from zope.dublincore.interfaces import IWriteZopeDublinCore

from zope.interface.interfaces import IMethod

from zope.proxy import isProxy
from zope.proxy import ProxyBase

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.assessment.interfaces import IQAssessment
from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IQEditableEvaluation
from nti.assessment.interfaces import IQAssessmentDateContext

from nti.base._compat import text_

from nti.base.interfaces import DEFAULT_CONTENT_TYPE

from nti.contentlibrary.bundle import BUNDLE_META_NAME

from nti.contentlibrary.dublincore import DCMETA_FILENAME

from nti.contentlibrary.interfaces import IDelimitedHierarchyKey
from nti.contentlibrary.interfaces import IEditableContentPackage
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
from nti.contenttypes.courses.interfaces import CourseSectionExporterExecutedEvent

from nti.contenttypes.courses.utils import get_course_vendor_info
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.ntiids.ntiids import hexdigest
from nti.ntiids.ntiids import hash_ntiid
from nti.ntiids.ntiids import make_ntiid

ID = StandardExternalFields.ID
OID = StandardExternalFields.OID
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE

INTERNAL_NTIID = StandardInternalFields.NTIID

_primitives = six.string_types + (Number, bool)

logger = __import__('logging').getLogger(__name__)


class ExportObjectProxy(ProxyBase):

    filer = property(
        lambda s: s.__dict__.get('_v_filer'),
        lambda s, v: s.__dict__.__setitem__('_v_filer', v))

    backup = property(
        lambda s: s.__dict__.get('_v_backup'),
        lambda s, v: s.__dict__.__setitem__('_v_backup', v))

    salt = property(
        lambda s: s.__dict__.get('_v_salt'),
        lambda s, v: s.__dict__.__setitem__('_v_salt', v))

    def __new__(cls, base, *unused_args, **unused_kwargs):
        return ProxyBase.__new__(cls, base)

    def __init__(self, base, filer=None, backup=True, salt=None):
        ProxyBase.__init__(self, base)
        self.salt = salt
        self.filer = filer
        self.backup = backup


def export_proxy(obj, filer=None, backup=False, salt=None):
    if not isinstance(obj,_primitives):
        return ExportObjectProxy(obj, filer, backup, salt)
    return obj


def proxy_params(obj):
    result = None
    if isProxy(obj, ExportObjectProxy):
        result = {
            'salt': obj.salt,
            'filer': obj.filer,
            'backup': obj.backup
        }
    return result or {}


@interface.implementer(ICourseSectionExporter)
class BaseSectionExporter(object):

    def _change_ntiid(self, ext_obj, salt=None):
        if isinstance(ext_obj, Mapping):
            # when not backing up make sure we take a hash of the current NTIID and
            # use it as the specific part for a new NTIID to make sure there are
            # fewer collisions when importing back
            for name in (NTIID, INTERNAL_NTIID):
                ntiid = ext_obj.get(name)
                if ntiid:
                    ext_obj[name] = self.hash_ntiid(ntiid, salt)
            for value in ext_obj.values():
                self._change_ntiid(value, salt)
        elif isinstance(ext_obj, (list, tuple, set)):
            for value in ext_obj:
                self._change_ntiid(value, salt)

    def hexdigest(self, data, salt=None):
        return hexdigest(data, salt)

    def hash_ntiid(self, ntiid, salt=None):
        return hash_ntiid(ntiid, salt)

    def hash_filename(self, name, salt=None):
        root, ext = os.path.splitext(name)
        root = self.hexdigest(root, salt)
        return root + ext

    def dump(self, ext_obj):
        source = cStringIO()
        simplejson.dump(ext_obj,
                        source,
                        indent='\t',
                        sort_keys=True)
        source.seek(0)
        return source

    def course_bucket(self, course):
        if ICourseSubInstance.providedBy(course):
            bucket = "%s/%s" % (SECTIONS, course.__name__)
        else:
            bucket = None
        return bucket

    @classmethod
    def proxy(cls, obj, filer=None, backup=False, salt=None):
        return export_proxy(obj, filer, backup, salt)


@interface.implementer(ICourseSectionExporter)
class CourseOutlineExporter(BaseSectionExporter):

    def asXML(self, outline, course=None, backup=False, salt=None):
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
                    if not backup:
                        src = self.hash_filename(node.src, salt)
                    else:
                        src = node.src
                    xml_node.setAttribute("src", src)
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

    def _export_remover(self, ext_obj, salt):
        if isinstance(ext_obj, Mapping):
            [ext_obj.pop(x, None) for x in (ID, OID, NTIID, INTERNAL_NTIID)]
            ContentNTIID = ext_obj.get('ContentNTIID', None)
            LessonOverviewNTIID = ext_obj.get('LessonOverviewNTIID', None)
            if ContentNTIID and ContentNTIID == LessonOverviewNTIID:
                ext_obj.pop('ContentNTIID', None)
            ext_obj.pop('LessonOverviewNTIID', None)
            src = ext_obj.get('src')
            if src:  # hash source
                src = self.hash_filename(src, salt)
                ext_obj['src'] = src
            for value in ext_obj.values():
                self._export_remover(value, salt)
        elif isinstance(ext_obj, (list, tuple, set)):
            for value in ext_obj:
                self._export_remover(value, salt)

    def export(self, context, filer, backup=True, salt=None):
        course = ICourseInstance(context)
        filer.default_bucket = bucket = self.course_bucket(course)
        # as json
        ext_obj = to_external_object(course.Outline,
                                     name='exporter',
                                     decorate=False)
        if not backup:
            self._export_remover(ext_obj, salt)
        # save
        source = self.dump(ext_obj)
        filer.save(COURSE_OUTLINE_NAME,
                   source,
                   contentType="application/json",
                   bucket=bucket,
                   overwrite=True)
        # as xml
        source = self.asXML(course.Outline,
                            course,
                            backup=backup,
                            salt=salt)
        filer.save("course_outline.xml",
                   source,
                   contentType="application/xml",
                   bucket=bucket,
                   overwrite=True)
        # process subinstances
        for sub_instance in get_course_subinstances(course):
            if sub_instance.Outline != course.Outline:
                self.export(sub_instance, filer, backup, salt)


@interface.implementer(ICourseSectionExporter)
class VendorInfoExporter(BaseSectionExporter):

    def export(self, context, filer, backup=True, salt=None):
        course = ICourseInstance(context)
        filer.default_bucket = bucket = self.course_bucket(course)
        vendor_info = get_course_vendor_info(course, False)
        if vendor_info:
            if not backup:
                # Pop invitation to avoid collision
                nti_map = vendor_info.get('NTI', {})
                nti_map.pop('Invitations', None)
            ext_obj = to_external_object(vendor_info,
                                         name="exporter",
                                         decorate=False)
            source = self.dump(ext_obj)
            filer.save(VENDOR_INFO_NAME,
                       source,
                       contentType="application/json",
                       bucket=bucket,
                       overwrite=True)
        for sub_instance in get_course_subinstances(course):
            self.export(sub_instance, filer, backup, salt)


@interface.implementer(ICourseSectionExporter)
class BundleMetaInfoExporter(BaseSectionExporter):

    def _get_package_ntiids(self, course, backup):
        """
        Get the bundle packages for export; we only need the content-backed
        packages if not backing up.
        """
        for package in get_course_packages(course):
            if backup:
                yield package.ntiid
            elif not IEditableContentPackage.providedBy(package):
                yield package.ntiid

    def export(self, context, filer, backup=True, salt=None):
        __traceback_info__ = context, backup, salt
        filer.default_bucket = None
        course = ICourseInstance(context)
        if ICourseSubInstance.providedBy(course):
            return
        entry = ICourseCatalogEntry(course)
        package_ntiids = list(self._get_package_ntiids(course, backup))
        data = {
            'ntiid': u'',
            'title': entry.Title,
            "ContentPackages": package_ntiids
        }
        ext_obj = to_external_object(data, decorate=False)
        source = self.dump(ext_obj)
        filer.save(BUNDLE_META_NAME, source,
                   contentType="application/json",
                   overwrite=True)


@interface.implementer(ICourseSectionExporter)
class BundleDCMetadataExporter(BaseSectionExporter):

    attr_to_xml = {
        'creators': 'creator',
        'subjects': 'subject',
        'contributors': 'contributors',
    }

    def _to_text(self, value):
        if isinstance(value, Number):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.strftime('%Y-%m-%d %H:%M:%S %Z')
        return value

    def export(self, context, filer, unused_backup=True, unused_salt=None):
        filer.default_bucket = None
        course = ICourseInstance(context)
        if ICourseSubInstance.providedBy(course):
            return
        entry = ICourseCatalogEntry(course)

        DOMimpl = minidom.getDOMImplementation()
        xmldoc = DOMimpl.createDocument(None, "metadata", None)
        doc_root = xmldoc.documentElement
        doc_root.setAttributeNS(None, "xmlns:dc",
                                "http://purl.org/dc/elements/1.1/")

        for k, v in IWriteZopeDublinCore.namesAndDescriptions(all=True):
            if IMethod.providedBy(v):
                continue
            value = getattr(entry, k, None) or getattr(entry, k.lower(), None)
            if value is None:
                continue
            k = k.lower()
            # create nodes
            if     isinstance(value, six.string_types) \
                or isinstance(value, (datetime, Number)):
                name = self.attr_to_xml.get(k, k)
                node = xmldoc.createElement("dc:%s" % name)
                node.appendChild(xmldoc.createTextNode(self._to_text(value)))
                doc_root.appendChild(node)
            elif isinstance(value, Iterable):
                for x in value:
                    name = self.attr_to_xml.get(k, k)
                    node = xmldoc.createElement("dc:%s" % name)
                    node.appendChild(xmldoc.createTextNode(self._to_text(x)))
                    doc_root.appendChild(node)

        source = xmldoc.toprettyxml(encoding="UTF-8")
        for name in (DCMETA_FILENAME, "bundle_dc_metadata.xml"):
            filer.save(name, source,
                       contentType="application/xml",
                       overwrite=True)


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

    def _guess_type(self, name):
        return mimetypes.guess_type(name)[0] or text_(DEFAULT_CONTENT_TYPE)

    def _process_root(self, root, bucket, filer):
        if IEnumerableDelimitedHierarchyBucket.providedBy(root):
            root_path = self._get_path(root)
            for child in root.enumerateChildren():
                if IDelimitedHierarchyKey.providedBy(child):
                    name = child.__name__
                    source = child.readContents()
                    bucket_path = bucket + root_path
                    contentType = self._guess_type(name)
                    filer.save(name, source, bucket=bucket_path,
                               contentType=contentType, overwrite=True)
                elif IEnumerableDelimitedHierarchyBucket.providedBy(child):
                    self._process_root(child, bucket, filer)

    def export(self, context, filer, unused_backup=True, unused_salt=None):
        course = ICourseInstance(context)
        filer.default_bucket = bucket = self.course_bucket(course)
        bucket = '' if not bucket else bucket + '/'
        presentation_resources = getattr(course, 'PlatformPresentationResources', None) \
                              or ICourseCatalogEntry(course).PlatformPresentationResources
        for resource in presentation_resources or ():
            self._process_root(resource.root, bucket, filer)


@interface.implementer(ICourseSectionExporter)
class RoleInfoExporter(BaseSectionExporter):

    def _role_interface_export(self, result, course, interface, *keys):
        roles = interface(course, None)
        if not roles:
            return
        for name in keys:
            deny = []
            allow = []
            for principal, setting in roles.getPrincipalsForRole(name) or ():
                pid = getattr(principal, 'id', str(principal))
                container = allow if setting == Allow else deny
                container.append(pid)
            if allow or deny:
                role_data = result[name] = {}
                for name, users in (('allow', allow), ('deny', deny)):
                    if users:
                        role_data[name] = users

    def _role_export_map(self, course):
        result = {}
        self._role_interface_export(result, course, IPrincipalRoleMap,
                                    RID_TA, RID_INSTRUCTOR)
        self._role_interface_export(result, course, IPrincipalRoleManager,
                                    RID_CONTENT_EDITOR)
        return result

    def export(self, context, filer, backup=True, salt=None):
        course = ICourseInstance(context)
        result = self._role_export_map(course)
        source = self.dump(result)
        filer.default_bucket = bucket = self.course_bucket(course)
        filer.save(ROLE_INFO_NAME, source, bucket=bucket,
                   contentType="application/json", overwrite=True)
        for sub_instance in get_course_subinstances(course):
            self.export(sub_instance, filer, backup, salt)


@interface.implementer(ICourseSectionExporter)
class AssignmentPoliciesExporter(BaseSectionExporter):

    def _process(self, course, backup=True, salt=None):
        result = {}
        policies = IQAssessmentPolicies(course)
        date_context = IQAssessmentDateContext(course)
        assignments = to_external_object(policies, decorate=False)
        date_context = to_external_object(date_context, decorate=False)

        # Merge the date context externalized dict into the
        # dict of assignments.
        for key, value in date_context.items():
            if key in assignments:
                assignments[key].update(value)
            else:
                assignments[key] = value

        # If not backing up, hash the ntiids if needed, as we export them
        if not backup:
            for key, value in assignments.items():
                assessment = component.queryUtility(IQAssessment, name=key)
                if IQEditableEvaluation.providedBy(assessment):
                    hashed_ntiid = self.hash_ntiid(key, salt)
                    result[hashed_ntiid] = value
                else:
                    result[key] = value
        else:
            result = assignments

        return result

    def export(self, context, filer, backup=True, salt=None):
        course = ICourseInstance(context)
        result = self._process(course, backup, salt)
        if result:
            source = self.dump(result)
            filer.default_bucket = bucket = self.course_bucket(course)
            filer.save(ASSIGNMENT_POLICIES_NAME,
                       source,
                       bucket=bucket,
                       contentType="application/json",
                       overwrite=True)
        for sub_instance in get_course_subinstances(course):
            self.export(sub_instance, filer, backup, salt)


@interface.implementer(ICourseSectionExporter)
class CourseInfoExporter(BaseSectionExporter):

    def export(self, context, filer, backup=True, salt=None):
        course = ICourseInstance(context)
        entry = ICourseCatalogEntry(course)
        ext_obj = to_external_object(entry,
                                     name="exporter",
                                     decorate=False)
        source = self.dump(ext_obj)
        filer.default_bucket = bucket = self.course_bucket(course)
        filer.save(CATALOG_INFO_NAME, source, bucket=bucket,
                   contentType="application/json", overwrite=True)
        for sub_instance in get_course_subinstances(course):
            self.export(sub_instance, filer, backup, salt)


@interface.implementer(ICourseExporter)
class CourseExporter(object):

    def export(self, context, filer, backup=True, salt=None):
        now = time.time()
        salt = salt or str(time.time())
        course = ICourseInstance(context)
        entry = ICourseCatalogEntry(course)
        for name, exporter in sorted(component.getUtilitiesFor(ICourseSectionExporter)):
            current = time.time()
            logger.info("Processing %s", name)
            try:
                exporter.export(course, filer, backup, salt)
                notify(CourseSectionExporterExecutedEvent(course, exporter, filer, backup, salt))
                logger.info("%s processed in %s(s)",
                            name, time.time() - current)
            except Exception as e:
                logger.exception("Error while processing %s", name)
                raise e
            filer.default_bucket = None  # restore
        notify(CourseInstanceExportedEvent(course))
        for subinstance in get_course_subinstances(course):
            notify(CourseInstanceExportedEvent(subinstance))
        logger.info("Course %s exported in %s(s)",
                    entry.ntiid, time.time() - now)

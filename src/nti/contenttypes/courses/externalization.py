#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import Mapping

from zope import component
from zope import interface

from zope.security.interfaces import IPrincipal

from nti.common.file import safe_filename

from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IInternalObjectExternalizer

from nti.mimetype import decorateMimeType

OID = StandardExternalFields.OID
CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

@component.adapter(ICourseInstanceEnrollmentRecord)
@interface.implementer(IInternalObjectExternalizer)
class _CourseInstanceEnrollmentRecordExternalizer(object):

	def __init__(self, obj):
		self.obj = obj

	def toExternalObject(self, **kwargs):
		result = LocatedExternalDict()
		result[MIMETYPE] = self.obj.mimeType
		result[CLASS] = "CourseInstanceEnrollmentRecord"
		# set fields
		result['Scope'] = self.obj.Scope
		principal = IPrincipal(self.obj.Principal, None)
		if principal is not None:
			result['Principal'] = principal.id
		entry = ICourseCatalogEntry(self.obj.CourseInstance, None)
		if entry is not None:
			result['Course'] = entry.ntiid
		return result

@component.adapter(ICourseOutlineNode)
@interface.implementer(IInternalObjectExternalizer)
class _CourseOutlineNodeExporter(object):

	def __init__(self, obj):
		self.node = obj

	def toExternalObject(self, **kwargs):
		mod_args = dict(**kwargs)
		mod_args['name'] = ''  # set default
		mod_args['decorate'] = False  # no decoration
		# use regular export
		result = to_external_object(self.node, **mod_args)
		if MIMETYPE not in result:
			decorateMimeType(self.node, result)
		if not getattr(self.node, 'LessonOverviewNTIID', None):
			result.pop('LessonOverviewNTIID', None)
		# make sure we provide an ntiid field
		if 'ntiid' not in result and getattr(self.node, 'ntiid', None):
			result['ntiid'] = self.node.ntiid
		# point to a valid .json source file
		name = result.get('src')
		if name:
			name = safe_filename(name)
			name = name + '.json' if not name.endswith('.json') else name
			result['src'] = name
		items = []
		# set again to exporter and export children
		mod_args['name'] = 'exporter'
		for node in self.node.values():
			ext_obj = to_external_object(node, **mod_args)
			items.append(ext_obj)
		if items:
			result[ITEMS] = items
		return result

@component.adapter(ICourseCatalogEntry)
@interface.implementer(IInternalObjectExternalizer)
class _CourseCatalogEntryExporter(object):
	
	REPLACE = ( 
		('Video', 'video'), ('Title', 'title'), ('Preview', 'isPreview'), 
		('StartDate', 'startDate'), ('EndDate', 'endDate'),
		('ProviderUniqueID', 'id'), ('ProviderDepartmentTitle', 'school'),
		('AdditionalProperties', 'additionalProperties'),
		('Credit', 'credit'), ('Instructors', 'instructors')
	)

	REQUIRED = {x[0] for x  in REPLACE}

	def __init__(self, obj):
		self.entry = obj

	def _remover(self, result, required=None):
		required = required or self.REQUIRED
		if isinstance(result, Mapping):
			for key in list(result.keys()) : # mutating
				if key not in required:
					result.pop(key, None)

	def _replacer(self, result, frm , to):
		if isinstance(result, Mapping) and frm in result:
			result[to] = result.pop(frm, None)
	
	def _fix_instructors(self, instructors):
		for instructor in instructors or ():
			self._remover(instructor, ('Name', 'JobTitle'))
			self._replacer(instructor, 'Name', 'name')
			self._replacer(instructor, 'JobTitle', 'title')

	def _fix_credits(self, data):
		for credit in data or ():
			self._remover(credit, ('Enrollment', 'Hours'))
			self._replacer(credit, 'Enrollment', 'enrollment')
			self._replacer(credit, 'Hours', 'hours')

	def toExternalObject(self, **kwargs):
		mod_args = dict(**kwargs)
		mod_args['name'] = ''  # set default
		mod_args['decorate'] = False  # no decoration
		result = to_external_object(self.entry, **mod_args)
		# remove unwanted keys
		self._remover(result) 
		# replace keys
		for frm, to in self.REPLACE:
			self._replacer(result, frm, to)
		# credit
		self._fix_credits(result.get('credit'))
		# instructors
		self._fix_instructors(result.get('instructors'))
		# extra keys
		result['is_non_public'] = INonPublicCourseInstance.providedBy(self.entry)
		return result

@component.adapter(ICourseInstanceVendorInfo)
@interface.implementer(IInternalObjectExternalizer)
class _CourseVendorInfoExporter(object):

	REMOVAL = (OID, CLASS, NTIID, CREATED_TIME, LAST_MODIFIED)

	def __init__(self, obj):
		self.obj = obj

	def _remover(self, result):
		if isinstance(result, Mapping):
			for key in list(result.keys()) : # mutating
				if key in self.REMOVAL:
					result.pop(key, None)
		return result

	def toExternalObject(self, **kwargs):
		mod_args = dict(**kwargs)
		mod_args['name'] = ''  # set default
		mod_args['decorate'] = False  # no decoration
		result = to_external_object(self.obj, **mod_args)
		self._remover(result)
		return result

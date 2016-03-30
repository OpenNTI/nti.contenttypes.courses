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

from zope.security.interfaces import IPrincipal

from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IInternalObjectExternalizer

from nti.mimetype import decorateMimeType

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE

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
		mod_args['name'] = '' # set default
		mod_args['decorate'] = False # no decoration
		# use regular export
		result = to_external_object(self.node, **mod_args)
		if MIMETYPE not in result:
			decorateMimeType(self.node, result)
		# make sure we provide an ntiid field
		if 'ntiid' not in result and getattr(self.node, 'ntiid', None):
			result['ntiid'] = self.node.ntiid
		items = []
		# set again to exporter and export children
		mod_args['name'] = 'exporter'
		for node in self.node.values():
			ext_obj = to_external_object(node, **mod_args)
			items.append(ext_obj)
		if items:
			result[ITEMS] = items
		return result

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
		result['Scope'] = self.obj.Scope
		result[MIMETYPE] = self.obj.mimeType
		result[CLASS] = "CourseInstanceEnrollmentRecord"
		result['Principal'] = IPrincipal(self.obj.Principal).id
		result['Course'] = ICourseCatalogEntry(self.obj.CourseInstance).ntiid
		return result

@component.adapter(ICourseOutlineNode)
@interface.implementer(IInternalObjectExternalizer)
class _CourseOutlineNodeExporter(object):

	def __init__(self, obj):
		self.node = obj

	def toExternalObject(self, **kwargs):
		mod_args = dict(**kwargs)
		mod_args['name'] = '' # set default
		# use regular export
		result = to_external_object(self.node, **mod_args)
		items = []
		# set again to exporter 
		mod_args['name'] = 'exporter'
		for node in self.node.values():
			ext_obj = to_external_object(node, **mod_args)
			items.append(ext_obj)
		if items:
			result[ITEMS] = items
		return result

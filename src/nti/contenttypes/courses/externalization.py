#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component
from zope.security.interfaces import IPrincipal

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IInternalObjectExternalizer

from .interfaces import ICourseCatalogEntry
from .interfaces import ICourseInstanceEnrollmentRecord

CLASS = StandardExternalFields.CLASS
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

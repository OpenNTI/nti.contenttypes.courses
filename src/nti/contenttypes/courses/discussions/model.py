#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.container.contained import Contained

from zope.mimetype.interfaces import IContentTypeAware

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.schema.schema import EqHash 
from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from .interfaces import ICourseDiscussion
	
@interface.implementer(ICourseDiscussion, IContentTypeAware)
@EqHash('id')
class CourseDiscussion(SchemaConfigured,
					   PersistentCreatedModDateTrackingObject,
					   Contained):
	createDirectFieldProperties(ICourseDiscussion)

	__external_class_name__ = u"Discussion"
	mime_type = mimeType = u'application/vnd.nextthought.courses.discussion'

	parameters = {}
	
	def __init__(self, *args, **kwargs):
		SchemaConfigured.__init__(self, *args, **kwargs)
		PersistentCreatedModDateTrackingObject.__init__(self, *args, **kwargs)

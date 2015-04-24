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

from zope.annotation.factory import factory as an_factory

from zope.container.contained import Contained

from zope.mimetype.interfaces import IContentTypeAware

from nti.dataserver.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.schema.schema import EqHash 
from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from ..interfaces import ICourseInstance

from .interfaces import ICourseDiscussion
from .interfaces import ICourseDiscussions
	
@interface.implementer(ICourseDiscussion, IContentTypeAware)
@EqHash('id')
class CourseDiscussion(SchemaConfigured,
					   PersistentCreatedModDateTrackingObject,
					   Contained):
	createDirectFieldProperties(ICourseDiscussion)

	__external_class_name__ = u"Discussion"
	mime_type = mimeType = u'application/vnd.nextthought.courses.discussion'

	parameters = {}
	
	_SET_CREATED_MODTIME_ON_INIT = False
	
	def __init__(self, *args, **kwargs):
		SchemaConfigured.__init__(self, *args, **kwargs)
		PersistentCreatedModDateTrackingObject.__init__(self, *args, **kwargs)
		
	def __str__(self, *args, **kwargs):
		if self.id:
			result = "%s(id=%s)" % (self.__class__.__name__, self.id)
		else:
			result = super(CourseDiscussion, self).__str__(self, *args, **kwargs)
		return result

	__repr__ = __str__
	
@component.adapter(ICourseInstance)
@interface.implementer(ICourseDiscussions)
class DefaultCourseDiscussions(CaseInsensitiveCheckingLastModifiedBTreeContainer):
	"""
	The default representation of course discussions.
	"""

	__name__ = None
	__parent__ = None
	
	def __init__(self):
		super(DefaultCourseDiscussions,self).__init__()

CourseDiscussions = an_factory(DefaultCourseDiscussions, 'CourseDiscussions')
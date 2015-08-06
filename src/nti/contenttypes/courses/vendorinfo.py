#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vendor information objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.annotation.factory import factory as an_factory

from persistent.mapping import PersistentMapping

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from .interfaces import ICourseInstance
from .interfaces import ICourseInstanceVendorInfo

@component.adapter(ICourseInstance)
@interface.implementer(ICourseInstanceVendorInfo)
class DefaultCourseInstanceVendorInfo(PersistentMapping,
									  PersistentCreatedAndModifiedTimeObject):
	"""
	The default representation of vendor info. We expect the info
	to be small.
	"""

	__parent__ = None
	__name__ = None

	# Leave these at 0 until they get set externally
	_SET_CREATED_MODTIME_ON_INIT = False

	def __init__(self):
		super(DefaultCourseInstanceVendorInfo, self).__init__()

VENDOR_INFO_KEY = 'CourseInstanceVendorInfo'
CourseInstanceVendorInfo = an_factory(DefaultCourseInstanceVendorInfo,
									  VENDOR_INFO_KEY)

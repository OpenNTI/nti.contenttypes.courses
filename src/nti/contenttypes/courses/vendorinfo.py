#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vendor information objects.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from persistent.mapping import PersistentMapping

from zope import component
from zope import interface

from zope.annotation.factory import factory as an_factory

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(ICourseInstanceVendorInfo)
class DefaultCourseInstanceVendorInfo(PersistentMapping,
                                      PersistentCreatedAndModifiedTimeObject):
    """
    The default representation of vendor info. We expect the info
    to be small.
    """

    __name__ = None
    __parent__ = None

    # Leave these at 0 until they get set externally
    _SET_CREATED_MODTIME_ON_INIT = False

    def __init__(self):  # pylint: disable=useless-super-delegation
        super(DefaultCourseInstanceVendorInfo, self).__init__()


VENDOR_INFO_KEY = 'CourseInstanceVendorInfo'
CourseInstanceVendorInfo = an_factory(DefaultCourseInstanceVendorInfo,
                                      VENDOR_INFO_KEY)

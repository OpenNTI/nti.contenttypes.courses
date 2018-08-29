#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contenttypes.courses.grading.interfaces import ICategoryGradeScheme

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import IInternalObjectUpdater

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICategoryGradeScheme)
@interface.implementer(IInternalObjectUpdater)
class _CategoryGradeSchemeUpdater(InterfaceObjectIO):

    _ext_iface_upper_bound = ICategoryGradeScheme

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        # If they give us a non-fractional weight, convert it.
        weight = parsed.get('Weight')
        if weight is not None and weight > 1:
            weight = round(weight / 100.0, 3)
            parsed['weight'] = weight
        return InterfaceObjectIO.updateFromExternalObject(self, parsed, *args, **kwargs)

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

from nti.externalization.interfaces import IInternalObjectUpdater

from nti.externalization.datastructures import InterfaceObjectIO

from .interfaces import IEqualGroupGrader

@interface.implementer(IInternalObjectUpdater)
@component.adapter(IEqualGroupGrader)
class _EqualGroupGraderUpdater(InterfaceObjectIO):

    _ext_iface_upper_bound = IEqualGroupGrader

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        result = super(_EqualGroupGraderUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
        groups = self._ext_self.groups or {}
        for name, weight in list(groups.items()):
            if weight > 1:
                groups[name] = round(float(weight)/100.0, 2)
        return result

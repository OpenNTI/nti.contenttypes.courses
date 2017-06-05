#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contenttypes.courses.grading.interfaces import IEqualGroupGrader

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import IInternalObjectUpdater

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object


@component.adapter(IEqualGroupGrader)
@interface.implementer(IInternalObjectUpdater)
class _EqualGroupGraderUpdater(InterfaceObjectIO):

    _ext_iface_upper_bound = IEqualGroupGrader

    def parseGroups(self, parsed):
        groups = parsed.get('Groups', {})
        for name, value in list(groups.items()):
            weight = value.get('Weight')
            if weight is not None and weight > 1:
                weight = round(weight / 100.0, 3)
                value['weight'] = weight
            groups[name] = scheme = find_factory_for(value)()
            update_from_external_object(scheme, value)
        return groups

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        self.parseGroups(parsed)
        return InterfaceObjectIO.updateFromExternalObject(self, parsed, *args, **kwargs)

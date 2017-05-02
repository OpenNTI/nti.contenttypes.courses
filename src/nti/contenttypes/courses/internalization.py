#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import Mapping

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import IInternalObjectUpdater
from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID


@component.adapter(ICourseOutlineNode)
@interface.implementer(IInternalObjectUpdater)
class _CourseOutlineNodeUpdater(InterfaceObjectIO):

    _ext_iface_upper_bound = ICourseOutlineNode

    @property
    def node(self):
        return self._ext_self

    def set_ntiid(self, parsed):
        if NTIID.lower() in parsed or NTIID in parsed:
            self.node.ntiid = parsed.get('ntiid') or parsed.get(NTIID)

    def set_locked(self, parsed):
        if not ICourseOutline.providedBy(self.node):
            locked = parsed.get('isLocked')
            if locked:
                self.node.lock(event=False)
            locked = parsed.get('isChildOrderLocked')
            if locked:
                self.node.childOrderLock(event=False)

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        clazz = self.__class__
        self.set_ntiid(parsed)
        self.set_locked(parsed)
        isPublished = parsed.get('isPublished')  # capture param
        result = clazz.updateFromExternalObject(self, parsed, *args, **kwargs)
        if ITEMS in parsed:
            for item in parsed.get(ITEMS) or ():
                # parse and update just in case
                if isinstance(item, Mapping):
                    factory = find_factory_for(item)
                    new_node = factory()
                    update_from_external_object(new_node, item, **kwargs)
                else:
                    new_node = item
                self.node.append(new_node)
        if      isPublished \
            and not ICourseOutline.providedBy(self.node) \
            and self.node.publishBeginning is None:
            self.node.publish(event=False)
        return result


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IInternalObjectUpdater)
class _CourseCatalogEntryUpdater(InterfaceObjectIO):

    _ext_iface_upper_bound = ICourseCatalogEntry

    def _quiet_delattr(self, o, k):
        try:
            delattr(o, k)
        except AttributeError:
            if k not in o.__dict__:
                return
            if hasattr(o, '_p_jar'):
                o._p_activate()
            o.__dict__.pop(k, None)
            if hasattr(o, '_p_jar'):
                o._p_changed = 1
        except TypeError:
            pass

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        clazz = self.__class__
        parsed = CaseInsensitiveDict(parsed)
        result = clazz.updateFromExternalObject(self, parsed, *args, **kwargs)
        return result

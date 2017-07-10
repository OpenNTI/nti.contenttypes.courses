#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementation of the course outline structure.

.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time
from functools import total_ordering

from zope import interface

from zope.annotation.interfaces import IAttributeAnnotatable

from zope.container.contained import Contained
from zope.container.contained import uncontained
from zope.container.constraints import checkObject

from zope.container.ordered import OrderedContainer  # this is persistent

from nti.base._compat import text_

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode
from nti.contenttypes.courses.interfaces import ICourseOutlineCalendarNode

from nti.coremetadata.interfaces import ILastModified

from nti.dataserver.interfaces import SYSTEM_USER_ID
from nti.dataserver.interfaces import ITitledDescribedContent

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.publishing.mixins import CalendarPublishableMixin

from nti.recorder.mixins import RecordableContainerMixin

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import AdaptingFieldProperty
from nti.schema.fieldproperty import createFieldProperties
from nti.schema.fieldproperty import createDirectFieldProperties

# We eqhash based on identity here, since we do not
# use these things as keys in maps and we are not
# concerned with determining if two objects are equal
# as much as we are if they are the same object. Since
# we register these objects, some low level zope.interface.registry
# structures *do* use these objects as keys; thus, we
# want the fastest hash implementation possible that
# does not load the state of our object.
# See:
# http://www.zodb.org/en/latest/guide/writing-persistent-objects.html#things-you-can-do-but-need-to-carefully-consider-advanced


@total_ordering
@interface.implementer(IAttributeAnnotatable)
class _AbstractCourseOutlineNode(Contained,
                                 RecordableContainerMixin,
                                 CalendarPublishableMixin):

    createFieldProperties(ITitledDescribedContent)
    createDirectFieldProperties(ICourseOutlineNode)

    __external_can_create__ = True

    creator = SYSTEM_USER_ID

    title = AdaptingFieldProperty(ICourseOutlineNode['title'])
    description = AdaptingFieldProperty(ITitledDescribedContent['description'])

    def append(self, node):
        try:
            name = node.ntiid
        except AttributeError:
            name = text_(str(len(self)))
        self[name] = node

    def rename(self, old, new):
        # remove no event
        item = self._data[old]
        del self._data[old]
        # replace in map
        item.__name__ = new
        self._data[new] = item
        # replace in array
        idx = self._order.index(old)
        self._order[idx] = new

    def _do_reorder(self, index, ntiid):
        old_keys = list(self.keys())
        old_keys.remove(ntiid)
        if index is not None and index < len(old_keys):
            # Slicing works even if index > len at this point.
            new_keys = old_keys[:index]
            new_keys.append(ntiid)
            new_keys.extend(old_keys[index:])
        else:
            # An index outside our boundary acts as an append.
            old_keys.append(ntiid)
            new_keys = old_keys
        self.updateOrder(new_keys)  # see OrderedContainer

    def insert(self, index, obj):
        if obj.ntiid not in list(self.keys()):
            self.append(obj)
        self._do_reorder(index, obj.ntiid)

    def __lt__(self, other):
        try:
            return (self.mimeType, self.ntiid) < (other.mimeType, other.ntiid)
        except AttributeError:
            return NotImplemented

    def __gt__(self, other):
        try:
            return (self.mimeType, self.ntiid) > (other.mimeType, other.ntiid)
        except AttributeError:
            return NotImplemented

    def _delitemf(self, key):
        del self._data[key]
        self._order.remove(key)

    def reset(self, event=True):
        keys = list(self)
        for k in keys:
            if event:
                del self[k]
            else:
                self._delitemf(k)
    clear = reset


@interface.implementer(ICourseOutlineNode, ILastModified)
class CourseOutlineNode(_AbstractCourseOutlineNode,
                        # order matters
                        PersistentCreatedModDateTrackingObject,
                        OrderedContainer):

    LessonOverviewNTIID = None

    # XXX This class used to be persistent. Although there were
    # never any references explicitly stored to them, because it
    # was persistent and is a Container, the intid utility grabbed
    # the children when IObjectAdded fired. Now that we're not
    # persistent, those instances in the intid BTree cannot be
    # correctly read. So we define a broken object replacement
    # that our DB class factory will use instead.
    # JAM: 20140714: This is turned off because we now need to be
    # able to persist these items. Not sure what the implications are for
    # alpha, which was the only place that saw this error? I don't remember
    # the exact details...have to wait and see.
    # _v_nti_pseudo_broken_replacement_name = str('CourseOutlineNode_BROKEN')
    def __setitem__(self, key, value):
        checkObject(self, key, value)
        super(CourseOutlineNode, self).__setitem__(key, value)
        self.updateLastMod()

    def __delitem__(self, key):
        uncontained(self[key], self, key)
        super(CourseOutlineNode, self).__delitem__(key)
        self.updateLastMod()

    def reset(self, event=True):
        super(CourseOutlineNode, self).reset(event=event)
        self.updateLastMod()
    clear = reset

    def updateLastMod(self, t=None):
        try:
            t = time.time() if t is None else t
            super(CourseOutlineNode, self).updateLastMod(t)
            self.__parent__.updateLastMod(t)
        except AttributeError:
            pass


@interface.implementer(ICourseOutlineCalendarNode)
class CourseOutlineCalendarNode(SchemaConfigured,
                                CourseOutlineNode):
    createDirectFieldProperties(ICourseOutlineCalendarNode)

    AvailableEnding = AdaptingFieldProperty(ICourseOutlineCalendarNode['AvailableEnding'])

    AvailableBeginning = AdaptingFieldProperty(ICourseOutlineCalendarNode['AvailableBeginning'])

    def __init__(self, *args, **kwargs):
        SchemaConfigured.__init__(self, *args, **kwargs)
        CourseOutlineNode.__init__(self)


@interface.implementer(ICourseOutlineContentNode)
class CourseOutlineContentNode(CourseOutlineCalendarNode):
    createDirectFieldProperties(ICourseOutlineContentNode)


@interface.implementer(ICourseOutline, ILastModified)
class CourseOutline(CourseOutlineNode,
                    PersistentCreatedModDateTrackingObject):
    createDirectFieldProperties(ICourseOutline)

    _SET_CREATED_MODTIME_ON_INIT = False
    __external_can_create__ = False

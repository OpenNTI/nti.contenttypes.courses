#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from persistent.list import PersistentList

from persistent.mapping import PersistentMapping

from ZODB.interfaces import IConnection

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.container.contained import Contained

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseTabPreferences

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(ICourseTabPreferences)
class CourseTabPreferences(PersistentCreatedAndModifiedTimeObject, Contained):

    mimeType = mime_type = "application/vnd.nextthought.courses.coursetabpreferences"

    creator = None

    def __init__(self):
        self.reset()
        super(CourseTabPreferences, self).__init__()

    def reset(self):
        self._order = PersistentList()
        self._names = PersistentMapping()

    @property
    def names(self):
        return dict(self._names)
    
    @names.setter
    def names(self, values):
        self.update_names(values)

    @property
    def order(self):
        return list(self._order)

    @order.setter
    def order(self, values):
        self.update_order(values)
    
    def update_names(self, names):
        # pylint: disable=attribute-defined-outside-init
        self._names = PersistentMapping()
        self._names.update(names)

    def update_order(self, order):
        if not isinstance(order, (tuple, list)):
            raise TypeError('order must be a tuple or a list.')
        # pylint: disable=attribute-defined-outside-init
        self._order = PersistentList()
        self._order.extend(order)

    def clear(self):
        self._names.clear()
        del self._order[:]

    def __nonzero__(self):
        return bool(self._names or self._order)
    __bool__ = __nonzero__


@component.adapter(ICourseInstance)
@interface.implementer(ICourseTabPreferences)
def tab_prefereneces_for_course(course, create=True):
    result = None
    KEY = u"CourseTabPreferences"
    annotations = IAnnotations(course)
    try:
        result = annotations[KEY]
    except KeyError:
        if create:
            result = CourseTabPreferences()
            annotations[KEY] = result
            result.__name__ = KEY
            result.__parent__ = course
            connection = IConnection(course, None)
            if connection is not None:
                # pylint: disable=too-many-function-args
                connection.add(result)
    return result
CourseTabPreferencesFactory = tab_prefereneces_for_course


def get_tab_preferences(course, inherit=False):
    """
    A utility that coudl be used to return an ICourseTabPreferences, which includes
    the parent's course tab names if the course is a child course and inherit is True.
    """
    return ICourseTabPreferences(course) if inherit is True \
                else tab_prefereneces_for_course(course)

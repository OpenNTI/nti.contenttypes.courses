#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from functools import total_ordering

from ZODB.interfaces import IConnection

from ZODB.POSException import ConnectionStateError

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.container.contained import Contained

from zope.mimetype.interfaces import IContentTypeAware

from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.schema.eqhash import EqHash

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

logger = __import__('logging').getLogger(__name__)


@EqHash('id')
@total_ordering
@interface.implementer(ICourseDiscussion, IContentTypeAware)
class CourseDiscussion(SchemaConfigured,
                       PersistentCreatedModDateTrackingObject,
                       Contained):
    createDirectFieldProperties(ICourseDiscussion)

    __external_class_name__ = "Discussion"
    mime_type = mimeType = 'application/vnd.nextthought.courses.discussion'

    parameters = {}  # IContentTypeAware

    creator = SYSTEM_USER_ID

    def __init__(self, *args, **kwargs):
        SchemaConfigured.__init__(self, *args, **kwargs)
        PersistentCreatedModDateTrackingObject.__init__(self, *args, **kwargs)

    def __str__(self, *unused_args, **unused_kwargs):
        try:
            clazz = self.__class__.__name__
            if self.id:
                result = "%s(id=%s)" % (clazz, self.id)
            else:
                result = '%s(title="%s")' % (clazz, self.title)
            return result
        except ConnectionStateError:
            return"<%s object at %s>" % (type(self).__name__, hex(id(self)))
    __repr__ = __str__

    def __lt__(self, other):
        try:
            return (self.mimeType, self.title) < (other.mimeType, other.title)
        except AttributeError:  # pragma: no cover
            return NotImplemented

    def __gt__(self, other):
        try:
            return (self.mimeType, self.title) > (other.mimeType, other.title)
        except AttributeError:  # pragma: no cover
            return NotImplemented


@interface.implementer(ICourseDiscussions)
class DefaultCourseDiscussions(CaseInsensitiveCheckingLastModifiedBTreeContainer):
    """
    The default representation of course discussions.
    """

    __external_class_name__ = "CourseDiscussions"
    mime_type = mimeType = 'application/vnd.nextthought.courses.discussions'

    __name__ = None
    __parent__ = None


@component.adapter(ICourseInstance)
@interface.implementer(ICourseDiscussions)
def discussions_for_course(course, create=True):
    result = None
    KEY = u'CourseDiscussions'
    annotations = IAnnotations(course)
    try:
        result = annotations[KEY]
    except KeyError:
        if create:
            result = DefaultCourseDiscussions()
            annotations[KEY] = result
            result.__name__ = KEY
            result.__parent__ = course
            # Deterministically add to our course db.
            # Sectioned courses would give us multiple
            # db error for some reason.
            # pylint: disable=too-many-function-args
            connection = IConnection(course, None)
            if connection is not None:
                connection.add(result)
    return result
_discussions_for_course = discussions_for_course

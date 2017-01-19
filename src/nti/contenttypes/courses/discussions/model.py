#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from functools import total_ordering

from zope import component
from zope import interface

from zope.annotation.factory import factory as an_factory

from zope.container.contained import Contained

from zope.mimetype.interfaces import IContentTypeAware

from ZODB.POSException import ConnectionStateError

from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.schema.eqhash import EqHash

from nti.schema.field import SchemaConfigured

from nti.schema.fieldproperty import createDirectFieldProperties


@EqHash('id')
@total_ordering
@interface.implementer(ICourseDiscussion, IContentTypeAware)
class CourseDiscussion(SchemaConfigured,
                       PersistentCreatedModDateTrackingObject,
                       Contained):
    createDirectFieldProperties(ICourseDiscussion)

    __external_class_name__ = u"Discussion"
    mime_type = mimeType = u'application/vnd.nextthought.courses.discussion'

    parameters = {}  # IContentTypeAware

    creator = SYSTEM_USER_ID

    def __init__(self, *args, **kwargs):
        SchemaConfigured.__init__(self, *args, **kwargs)
        PersistentCreatedModDateTrackingObject.__init__(self, *args, **kwargs)

    def __str__(self, *args, **kwargs):
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
        except AttributeError:
            return NotImplemented

    def __gt__(self, other):
        try:
            return (self.mimeType, self.title) > (other.mimeType, other.title)
        except AttributeError:
            return NotImplemented


@component.adapter(ICourseInstance)
@interface.implementer(ICourseDiscussions)
class DefaultCourseDiscussions(CaseInsensitiveCheckingLastModifiedBTreeContainer):
    """
    The default representation of course discussions.
    """

    __external_class_name__ = u"CourseDiscussions"
    mime_type = mimeType = u'application/vnd.nextthought.courses.discussions'

    __name__ = None
    __parent__ = None

    def __init__(self):
        super(DefaultCourseDiscussions, self).__init__()

CourseDiscussions = an_factory(DefaultCourseDiscussions, 'CourseDiscussions')

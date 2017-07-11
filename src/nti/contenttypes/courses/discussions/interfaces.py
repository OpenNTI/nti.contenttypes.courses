#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.container.constraints import contains
from zope.container.interfaces import IContainer

from zope.interface.common.sequence import ISequence

from zope.location.interfaces import IContained

from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

from nti.base.interfaces import IFile
from nti.base.interfaces import ITitled
from nti.base.interfaces import ICreated
from nti.base.interfaces import ILastModified

from nti.contenttypes.courses.discussions.schema import DiscussionModeledContentBody

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.coremetadata.interfaces import ITaggedContent

from nti.namedfile.interfaces import IFileConstrained

from nti.schema.field import Choice
from nti.schema.field import Object
from nti.schema.field import Variant
from nti.schema.field import ValidURI
from nti.schema.field import ListOrTuple
from nti.schema.field import ValidTextLine

NTI_COURSE_BUNDLE = u'nti-course-bundle'
NTI_COURSE_BUNDLE_REF = u"%s://" % NTI_COURSE_BUNDLE

ALL_SCOPES_VOCABULARY = SimpleVocabulary([SimpleTerm(ES_ALL)] +
                                         list(ENROLLMENT_SCOPE_VOCABULARY))


def href_schema_field(title=u'', required=False, default=None):
    return Variant((ValidTextLine(title=u"href name"),
                    ValidURI(title=u"href source uri"),
                    Object(IFile, title=u"href file")),
                   title=title,
                   default=default,
                   required=required)


class ICourseDiscussion(ITitled, ITaggedContent, ILastModified,
                        IContained, ICreated, IFileConstrained):

    title = ValidTextLine(title=u"Discussion title", required=True)

    icon = href_schema_field(title=u"Discussion icon href")

    label = ValidTextLine(title=u"The label", required=False, default=u'')

    body = DiscussionModeledContentBody(required=False)

    scopes = ListOrTuple(Choice(vocabulary=ALL_SCOPES_VOCABULARY),
                         title=u'scopes', required=True, min_length=1)

    id = ValidTextLine(title=u"Internal id", required=False)
    id.setTaggedValue('_ext_excluded_out', True)


class ICourseDiscussions(IContainer, IContained, ILastModified):
    """
    A container for all the discussions
    """
    contains('.ICourseDiscussion')

    def clear():
        """
        clear all entries in this Container
        """


class ICourseDiscussionList(ISequence):
    """
    A marker interface for a sequence of course discussion objects
    """


class ICourseDiscussionTopic(interface.Interface):
    """
    A marker interface for a created topics
    """

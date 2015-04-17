#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.container.constraints import contains
from zope.container.interfaces import IContainer

from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

from zope.location.interfaces import IContained

from nti.coremetadata.interfaces import ITitled
from nti.coremetadata.interfaces import ILastModified

from nti.dataserver.fragments.schema import CompoundModeledContentBody

from nti.schema.field import Choice
from nti.schema.field import ListOrTuple
from nti.schema.field import ValidTextLine

from ..interfaces import ENROLLMENT_SCOPE_VOCABULARY

NTI_COURSE_BUNDLE = u'nti-course-bundle'

SCOPES_VOCABULARY = SimpleVocabulary( [SimpleTerm(u'All')] + list(ENROLLMENT_SCOPE_VOCABULARY))
	
class ICourseDiscussion(ITitled, ILastModified, IContained):
	title = ValidTextLine(title="Discussion title", required=True)
	icon = ValidTextLine(title="Discussion icon href", required=False)
	label = ValidTextLine(title="The label", required=False, default=u'')
	body = CompoundModeledContentBody(required=False)
	scopes = ListOrTuple(Choice(vocabulary=SCOPES_VOCABULARY),
						 title='scopes', required=True, min_length=1)
	
	id = ValidTextLine(title="Internal id", required=False)
	id.setTaggedValue('_ext_excluded_out', True)


class ICourseDiscussions(IContainer, IContained):
	"""
	A container for all the discussions
	"""
	contains(str('.ICourseDiscussion'))

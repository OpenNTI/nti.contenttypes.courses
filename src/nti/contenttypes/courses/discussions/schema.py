#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.coremetadata.schema import CompoundModeledContentBody
from nti.coremetadata.schema import legacyModeledContentBodyTypes

from nti.schema.field import ValidText


def discussionModeledContentBodyTypes():
    result = legacyModeledContentBodyTypes()
    result.append(ValidText(min_length=1, 
                            description=u"A text that is non-empty"))
    return result


def DiscussionModeledContentBody(required=False):
    return CompoundModeledContentBody(required=required,
                                      fields=discussionModeledContentBodyTypes())

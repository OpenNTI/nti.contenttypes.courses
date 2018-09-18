#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.coremetadata.schema import legacyModeledContentBodyTypes
from nti.coremetadata.schema import ExtendedCompoundModeledContentBody

from nti.schema.field import ValidText

logger = __import__('logging').getLogger(__name__)


def discussionModeledContentBodyTypes():
    result = legacyModeledContentBodyTypes()
    result.append(ValidText(min_length=1, 
                            description=u"A text that is non-empty"))
    return result


def DiscussionModeledContentBody(required=False):
    return ExtendedCompoundModeledContentBody(required=required,
                                              fields=discussionModeledContentBodyTypes())

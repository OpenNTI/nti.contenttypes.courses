#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: model.py 123306 2017-10-19 03:47:14Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.contenttypes.courses.interfaces import ICourseAwardableCredit

from nti.contenttypes.credit.credit import AwardableCredit

from nti.externalization.representation import WithRepr

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

logger = __import__('logging').getLogger(__name__)


@WithRepr
@interface.implementer(ICourseAwardableCredit)
class CourseAwardableCredit(AwardableCredit):
    createDirectFieldProperties(ICourseAwardableCredit)

    scope = None
    mimeType = mime_type = "application/vnd.nextthought.credit.courseawardablecredit"

    def __init__(self, *args, **kwargs):
        super(CourseAwardableCredit, self).__init__(*args, **kwargs)
        SchemaConfigured.__init__(self, *args, **kwargs)


import zope.deferredimport
zope.deferredimport.initialize()

zope.deferredimport.deprecatedFrom(
    "moved to nti.app.products.courseware.credit",
    "nti.app.products.courseware.credit",
    "CourseAwardedCredit")

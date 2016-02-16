#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
General objects and support for courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

from nti.contenttypes.courses.utils import get_courses_catalog
from nti.contenttypes.courses.utils import get_course_vendor_info
from nti.contenttypes.courses.utils import get_enrollment_catalog

from nti.contenttypes.courses.vendorinfo import VENDOR_INFO_KEY

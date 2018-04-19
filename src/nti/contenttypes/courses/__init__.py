#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

from nti.contenttypes.courses.index import get_courses_catalog
from nti.contenttypes.courses.index import get_enrollment_catalog

from nti.contenttypes.courses.utils import get_course_vendor_info

from nti.contenttypes.courses.vendorinfo import VENDOR_INFO_KEY

#: Course bundle NTIID type
COURSE_BUNDLE_TYPE = 'Bundle:CourseBundle'

#: Course role info file name
ROLE_INFO_NAME = 'role_info.json'

#: Course vendor info file name
VENDOR_INFO_NAME = 'vendor_info.json'

#: Course catalog/course info file name
CATALOG_INFO_NAME = 'course_info.json'

#: Course outline file name
COURSE_OUTLINE_NAME = 'course_outline.json'

#: Course grading policy file name
GRADING_POLICY_NAME = 'grading_policy.json'

#: Course instructor info file name
INSTRUCTOR_INFO_NAME = 'instructor_info.json'

#: Course assignment policies file name
ASSIGNMENT_POLICIES_NAME = ASSIGNMENT_DATES_NAME = 'assignment_policies.json'

#: Course evaluations
EVALUATION_INDEX = 'evaluation_index.json'

#: Course evaluation last modified annotation key
EVALUATION_INDEX_LAST_MODIFIED = EVALUATION_INDEX + '.lastModified'

#: Export a seed to validate an export is only used once per environment
COURSE_EXPORT_HASH_FILE = 'course_export_hash.txt'

#: Course meta-info file name.
COURSE_META_NAME = u'meta_info.json'

#: Course meta-info export-hash key.
EXPORT_HASH_KEY  = u'ExportHash'

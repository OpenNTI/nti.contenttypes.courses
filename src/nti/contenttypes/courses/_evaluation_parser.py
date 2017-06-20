#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.annotation.interfaces import IAnnotations

from nti.contenttypes.courses import EVALUATION_INDEX_LAST_MODIFIED

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEvaluationImporter


def get_index_lastModified(context):
    course = ICourseInstance(context)
    annotations = IAnnotations(course)
    return annotations.get(EVALUATION_INDEX_LAST_MODIFIED) or 0


def set_index_lastModified(context, last_modified):
    course = ICourseInstance(context)
    annotations = IAnnotations(course)
    annotations[EVALUATION_INDEX_LAST_MODIFIED] = last_modified


def fill_evaluations_from_key(course, key, force=False):
    last_modified = get_index_lastModified(course)
    if not force and key.lastModified <= last_modified:
        return False

    importer = component.queryUtility(ICourseEvaluationImporter)
    if importer is None:
        return False

    entry = ICourseCatalogEntry(course)
    logger.info('Updating course evaluations for %s', entry.ntiid)

    __traceback_info__ = key, entry
    importer.process_source(course, key)
    set_index_lastModified(course, key.lastModified)
    return True

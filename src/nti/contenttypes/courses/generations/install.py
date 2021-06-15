#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generations for managing courses.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope.intid.interfaces import IIntIds

from zope.generations.generations import SchemaManager

from nti.contenttypes.courses.index import install_courses_catalog
from nti.contenttypes.courses.index import install_enrollment_catalog
from nti.contenttypes.courses.index import install_enrollment_meta_catalog
from nti.contenttypes.courses.index import install_course_outline_catalog

generation = 50

logger = __import__('logging').getLogger(__name__)


class _CoursesSchemaManager(SchemaManager):
    """
    A schema manager that we can register as a utility in ZCML.
    """

    def __init__(self):
        super(_CoursesSchemaManager, self).__init__(
            generation=generation,
            minimum_generation=generation,
            package_name='nti.contenttypes.courses.generations')


def install_catalog(context):
    conn = context.connection
    root = conn.root()
    dataserver_folder = root['nti.dataserver']
    lsm = dataserver_folder.getSiteManager()
    intids = lsm.getUtility(IIntIds)
    install_courses_catalog(dataserver_folder, intids)
    install_enrollment_catalog(dataserver_folder, intids)
    install_enrollment_meta_catalog(dataserver_folder, intids)
    install_course_outline_catalog(dataserver_folder, intids)


def evolve(context):
    install_catalog(context)

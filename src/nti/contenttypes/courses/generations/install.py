#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generations for managing courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 3

import zope.intid

from zope.generations.generations import SchemaManager

from ..index import install_enrollment_catalog

class _CoursesSchemaManager(SchemaManager):
	"""
	A schema manager that we can register as a utility in ZCML.
	"""

	def __init__(self):
		super(_CoursesSchemaManager, self).__init__(generation=generation,
													minimum_generation=generation,
													package_name='nti.contenttypes.courses.generations')

def evolve(context):
	install_catalog(context)

def install_catalog(context):
	conn = context.connection
	root = conn.root()
	dataserver_folder = root['nti.dataserver']
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(zope.intid.IIntIds)
	install_enrollment_catalog(dataserver_folder, intids)

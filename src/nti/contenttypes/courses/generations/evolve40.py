#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.contenttypes.courses.index import IX_IMPORT_HASH
from nti.contenttypes.courses.index import CourseImportHashIndex
from nti.contenttypes.courses.index import install_courses_catalog

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

generation = 40

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
              "Hooks not installed?"

        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)

        catalog = install_courses_catalog(ds_folder, intids)
        if IX_IMPORT_HASH not in catalog:
            index = CourseImportHashIndex(family=intids.family)
            intids.register(index)
            locate(index, catalog, IX_IMPORT_HASH)
            catalog[IX_IMPORT_HASH] = index

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 40 by adding course import hash index to the courses catalog.
    """
    do_evolve(context, generation)

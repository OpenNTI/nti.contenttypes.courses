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

from nti.contenttypes.courses.interfaces import ICourseCatalog,\
    IGlobalCourseCatalog

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites
from nti.intid.common import addIntId

generation = 33

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


def process_site(intids):
    course_catalog = component.queryUtility(ICourseCatalog)
    if      course_catalog \
        and not course_catalog.isEmpty() \
        and not IGlobalCourseCatalog.providedBy(course_catalog):
        for entry in course_catalog.iterCatalogEntries():
            doc_id = intids.queryId(entry)
            if doc_id is None:
                addIntId(entry)


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

        for site in get_all_host_sites():
            with current_site(site):
                process_site(intids)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 33 by giving ICourseCatalogEntry objects intids.
    """
    do_evolve(context, generation)

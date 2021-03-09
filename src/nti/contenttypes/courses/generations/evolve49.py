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

from nti.contenttypes.courses.index import IX_ENROLLMENT_COUNT,\
    install_enrollment_meta_catalog, EnrollmentCountIndex

from nti.contenttypes.courses.index import install_enrollment_meta_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IGlobalCourseCatalog

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

generation = 49

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


def process_site(intids, seen, new_indexes):
    def do_index_entry(entry):
        course = ICourseInstance(entry, None)
        course_doc_id = intids.queryId(course)
        for idx in new_indexes:
            idx.index_doc(course_doc_id, course)

    course_catalog = component.queryUtility(ICourseCatalog)
    if      course_catalog \
        and not course_catalog.isEmpty() \
        and not IGlobalCourseCatalog.providedBy(course_catalog):
        for entry in course_catalog.iterCatalogEntries():
            doc_id = intids.queryId(entry)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            do_index_entry(entry)


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
        catalog = install_enrollment_meta_catalog(ds_folder, intids)
        if IX_ENROLLMENT_COUNT not in catalog:
            new_idx = EnrollmentCountIndex(family=intids.family)
            intids.register(new_idx)
            locate(new_idx, catalog, IX_ENROLLMENT_COUNT)
            catalog[IX_ENROLLMENT_COUNT] = new_idx
        seen = set()
        new_idx = catalog[IX_ENROLLMENT_COUNT]
        for site in get_all_host_sites():
            with current_site(site):
                logger.info("Processing site (%s)", site.__name__)
                process_site(intids, seen, (new_idx,))

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 49 by building the enrollment meta catalog.
    """
    do_evolve(context, generation)

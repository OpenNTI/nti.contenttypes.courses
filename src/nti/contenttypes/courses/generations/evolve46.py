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

from nti.contenttypes.courses.index import IX_ENTRY_PUID
from nti.contenttypes.courses.index import IX_ENTRY_DESC
from nti.contenttypes.courses.index import IX_ENTRY_TITLE
from nti.contenttypes.courses.index import IX_ENTRY_START_DATE
from nti.contenttypes.courses.index import IX_ENTRY_END_DATE
from nti.contenttypes.courses.index import IX_ENTRY_TITLE_SORT
from nti.contenttypes.courses.index import IX_ENTRY_PUID_SORT
from nti.contenttypes.courses.index import IX_ENTRY_TO_COURSE_INTID
from nti.contenttypes.courses.index import IX_COURSE_TO_ENTRY_INTID

from nti.contenttypes.courses.index import CourseToEntryIntidIndex
from nti.contenttypes.courses.index import EntryToCourseIntidIndex
from nti.contenttypes.courses.index import install_courses_catalog
from nti.contenttypes.courses.index import CourseCatalogEntryDescriptionIndex
from nti.contenttypes.courses.index import CourseCatalogEntryPUIDIndex
from nti.contenttypes.courses.index import CourseCatalogEntryTitleIndex
from nti.contenttypes.courses.index import CourseCatalogEntryPUIDSortIndex
from nti.contenttypes.courses.index import CourseCatalogEntryTitleSortIndex
from nti.contenttypes.courses.index import CourseCatalogEntryStartDateIndex
from nti.contenttypes.courses.index import CourseCatalogEntryEndDateIndex

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

generation = 46

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


def process_site(intids, seen, catalog):
    course_catalog = component.queryUtility(ICourseCatalog)
    if course_catalog and not course_catalog.isEmpty():
        for entry in course_catalog.iterCatalogEntries():
            doc_id = intids.queryId(entry)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            catalog.index_doc(doc_id, entry)
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(entry)
            if doc_id is not None:
                catalog.index_doc(doc_id, course)


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
        for key, idx in ((IX_ENTRY_TITLE, CourseCatalogEntryTitleIndex),
                         (IX_ENTRY_DESC, CourseCatalogEntryDescriptionIndex),
                         (IX_ENTRY_PUID, CourseCatalogEntryPUIDIndex),
                         (IX_ENTRY_TITLE_SORT, CourseCatalogEntryTitleSortIndex),
                         (IX_ENTRY_PUID_SORT, CourseCatalogEntryPUIDSortIndex),
                         (IX_ENTRY_START_DATE, CourseCatalogEntryStartDateIndex),
                         (IX_ENTRY_TO_COURSE_INTID, EntryToCourseIntidIndex),
                         (IX_COURSE_TO_ENTRY_INTID, CourseToEntryIntidIndex),
                         (IX_ENTRY_END_DATE, CourseCatalogEntryEndDateIndex)):
            if key not in catalog:
                new_idx = idx(family=intids.family)
                intids.register(new_idx)
                locate(new_idx, catalog, key)
                catalog[key] = new_idx

        seen = set()
        for site in get_all_host_sites():
            with current_site(site):
                process_site(intids, seen, catalog)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 46 by indexing more catalog entry attributes. We also
    index the course-to-entry intids and vice versa.
    """
    do_evolve(context, generation)

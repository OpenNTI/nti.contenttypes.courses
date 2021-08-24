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

from nti.contenttypes.courses.index import IX_TAGS

from nti.contenttypes.courses.index import get_courses_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

generation = 53

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


def process_course(entry, course, intids, idx):
    result = 0
    for section_course in get_course_subinstances(course):
        section_entry = ICourseCatalogEntry(section_course)
        if section_entry.tags is entry.tags:
            result += 1
            entry_id = intids.queryId(section_entry)
            idx.index_doc(entry_id, section_entry)
    return result


def process_site(intids, seen, idx):
    course_catalog = component.queryUtility(ICourseCatalog)
    result = 0
    if course_catalog and not course_catalog.isEmpty():
        for entry in course_catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            result += process_course(entry, course, intids, idx)
    return result


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
        catalog = get_courses_catalog()
        # Only index the tag idx
        idx = catalog[IX_TAGS]

        seen = set()
        sites = get_all_host_sites()
        updated_count = 0
        for site in sites:
            with current_site(site):
                updated_count += process_site(intids, seen, idx)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done. Indexed %s courses in %s sites',
                generation, updated_count, len(sites))


def evolve(context):
    """
    Evolve to generation 53 by indexing subinstances with the same `tags`
    instance as it's parent entry.
    """
    do_evolve(context, generation)

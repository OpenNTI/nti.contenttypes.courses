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

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

generation = 52

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


def process_course(course):
    result = False
    course_root = course.root
    if course_root is not None and 'absolute_path' in course_root.__dict__:
        del course_root.__dict__['absolute_path']
        result = True
    return result


def process_site(intids, seen, updated):
    course_catalog = component.queryUtility(ICourseCatalog)
    if course_catalog and not course_catalog.isEmpty():
        for entry in course_catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            if process_course(course):
                updated.add(doc_id)


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

        seen = set()
        sites = get_all_host_sites()
        updated = set()
        for site in sites:
            with current_site(site):
                process_site(intids, seen, updated)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.  Updated %s courses in %s sites',
                generation, len(updated), len(sites))


def evolve(context):
    """
    Evolve to generation 52 by removing the `absolute_path` from the course.root dict.
    This should be lazily generated.
    """
    do_evolve(context, generation)

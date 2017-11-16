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
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IGlobalCourseCatalog

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

generation = 36

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
    try:
        result = True
        bundle = course.ContentPackageBundle
        if bundle.root is None:
            bundle.root = course.root
        elif not ICourseSubInstance.providedBy(course):
            # bundle root and course root must be the same
            if bundle.root != course.root:
                bundle.root = course.root
            else:
                result = False
        else:
            root = course.root
            parent = get_parent_course(course)
            # check there are local presentation assets
            if      root is not None \
                and root.getChildNamed('presentation-assets') is not None:
                bundle.root = root
            else:
                # bundle is defined but not valid presentation assets in it
                if      bundle.root is not None \
                    and bundle.root.getChildNamed('presentation-assets') is None:
                    bundle.root = course.root
                # if bundle root is not parent's root
                if bundle.root != parent.root:
                    # bundle root is not the course root or 
                    # there are no presentation assets in it
                    # bundle root and course root must be the same
                    if     root is None \
                        or root.getChildNamed('presentation-assets') is None \
                        or bundle.root != course.root:
                        bundle.root = parent.root  # use parent
                else:
                    result = False
    except AttributeError:
        result = False
    if result:
        entry = ICourseCatalogEntry(course)
        logger.warn("Bundle root adjusted for course %s", entry.ntiid)
    return result


def process_site(intids, seen):
    count = 0
    catalog = component.queryUtility(ICourseCatalog)
    if not catalog or IGlobalCourseCatalog.providedBy(catalog):
        return count
    else:
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if     doc_id is None or doc_id in seen \
                or ILegacyCourseInstance.providedBy(course) \
                or ICourseSubInstance.providedBy(course):
                continue
            seen.add(doc_id)
            for course in get_course_hierarchy(course):
                if process_course(course):
                    count += 1
    return count


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

        count = 0
        seen = set()
        for site in get_all_host_sites():
            with current_site(site):
                count += process_site(intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done. %s course(s) processed',
                generation, count)


def evolve(context):
    """
    Evolve to generation 36 by fixing roots of course content bundles
    """
    do_evolve(context, generation)

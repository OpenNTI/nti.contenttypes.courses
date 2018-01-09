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

from nti.contenttypes.courses import COURSE_BUNDLE_TYPE

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IGlobalCourseCatalog

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.ntiids.ntiids import get_type
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_specific

from nti.site.hostpolicy import get_all_host_sites

generation = 38

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


def process_course(entry, course):
    entry_ntiid = entry.ntiid
    entry_nttype = get_type(entry_ntiid)
    try:
        bundle = course.ContentPackageBundle
        bundle_ntiid = bundle.ntiid
        if bundle_ntiid:
            # derive a entry ntiid from a bundle ntiid
            bundle_specific = get_specific(bundle_ntiid)
            ntiid = make_ntiid(nttype=entry_nttype,
                               base=bundle_ntiid,
                               specific=bundle_specific)
        else:
            ntiid = None
        if ntiid != entry_ntiid:
            specific = get_specific(entry_ntiid)
            ntiid = make_ntiid(nttype=COURSE_BUNDLE_TYPE,
                               specific=specific,
                               base=entry_ntiid)
            bundle.ntiid = ntiid
            return True
    except AttributeError:  # pragma: no cover
        pass
    return False


def process_site(intids, seen):
    count = 0
    catalog = component.queryUtility(ICourseCatalog)
    if      catalog is not None \
        and not catalog.isEmpty() \
        and not IGlobalCourseCatalog.providedBy(catalog):
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen \
                    or ILegacyCourseInstance.providedBy(course):
                continue
            seen.add(doc_id)
            if process_course(entry, course):
                count += 1
    return count


def do_evolve(context, generation=generation):  # pylint: disable=redefined-outer-name
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
    logger.info('Evolution %s done. %s course bundle(s) processed',
                generation, count)


def evolve(context):
    """
    Evolve to generation 38 by fixing course bundle ntiids
    """
    do_evolve(context, generation)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 28

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.courses._bundle import CoursePersistentContentPackageBundle


from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites


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


def _update_bundle(seen, catalog, intids):
    for entry in catalog.iterCatalogEntries():
        if entry.ntiid in seen:
            continue
        seen.add(entry.ntiid)
        course = ICourseInstance(entry, None)
        if course is not None and not ICourseSubInstance.providedBy(course):
            bundle = course.ContentPackageBundle
            if      bundle is not None and \
                not isinstance(bundle, CoursePersistentContentPackageBundle):
                new_bundle = CoursePersistentContentPackageBundle()
                new_bundle.root = bundle.root
                new_bundle.__parent__ = course
                new_bundle.ntiid =  bundle.ntiid 
                new_bundle.createdTime = bundle.createdTime
                new_bundle.lastModified = bundle.lastModified
                # update
                bundle.__parent__ = None
                course.ContentPackageBundle = new_bundle
                # check intid
                doc_id = intids.queryId(bundle)
                if doc_id is not None:
                    intids.unregister(bundle)
                    intids.register(new_bundle)

def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert   component.getSiteManager() == ds_folder.getSiteManager(), \
                "Hooks not installed?"

        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        
        seen = set()
        # global library
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is not None:
            _update_bundle(seen, catalog, intids)
        for site in get_all_host_sites():
            with current_site(site):
                catalog = component.queryUtility(ICourseCatalog)
                if catalog is not None:
                    _update_bundle(seen, catalog, intids)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 28 by recreating the course pkg bundles.
    """
    do_evolve(context, generation)

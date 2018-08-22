#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id:$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import IContentCourseInstance
from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.metadata.index import IX_MIMETYPE
from nti.dataserver.metadata.index import get_metadata_catalog

from nti.site.hostpolicy import get_all_host_sites

logger = __import__('logging').getLogger(__name__)

generation = 42


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warning("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def _load_library():
    library = component.queryUtility(IContentPackageLibrary)
    if library is not None:
        library.syncContentPackages()


def _process_site(current_site, intids, seen):
    with site(current_site):
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is None or catalog.isEmpty():
            return
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            if     ICourseSubInstance.providedBy(course) \
                or not IContentCourseInstance.providedBy(course):
                continue
            # check bundle
            bundle = course.ContentPackageBundle
            if bundle is None:
                logger.warning("Course %s does not have a bundle", entry.ntiid)
            doc_id = intids.queryId(bundle)
            if doc_id is None:
                bundle.__parent__ = course
                lifecycleevent.added(bundle, course)
                logger.info("Indexig bundle for %s", entry.ntiid)
            else:  # catalogs may be out of sync
                lifecycleevent.modified(bundle)


def remove_invalid_bundles(intids):
    catalog = get_metadata_catalog()
    query = {
        IX_MIMETYPE:
             {'any_of': ('application/vnd.nextthought.coursecontentpackagebundle',)}}
    for doc_id in catalog.apply(query) or ():
        obj = intids.queryObject(doc_id)
        if not ICourseContentPackageBundle.providedBy(obj):
            continue
        course = obj.__parent__  # by definition
        # course deleted
        if course is not None and intids.queryId(course) is None:
            obj.__parent__ = None
            lifecycleevent.removed(obj)
            logger.warning("Removing bundle with id %s", doc_id)


def do_evolve(context):
    setHooks()
    conn = context.connection
    root = conn.root()
    dataserver_folder = root['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = dataserver_folder
    component.provideUtility(mock_ds, IDataserver)

    with site(dataserver_folder):
        assert component.getSiteManager() == dataserver_folder.getSiteManager(), \
               "Hooks not installed?"

        seen = set()
        lsm = dataserver_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)

        _load_library()
        logger.info('Evolution %s started.', generation)

        # remove bundles for deleted courses
        remove_invalid_bundles(intids)

        # index bundles
        for current_site in get_all_host_sites():
            _process_site(current_site, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done', generation)


def evolve(context):
    """
    Evolve to 42 by making sure we remove bundles for deleted course and give
    intids to those without
    """
    do_evolve(context)

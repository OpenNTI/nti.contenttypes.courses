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

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.index import IX_TAGS
from nti.contenttypes.courses.index import install_courses_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

generation = 45

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

        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            library.syncContentPackages()

        logger.info('Evolution %s started.', generation)

        catalog = install_courses_catalog(ds_folder, intids)
        idx = catalog[IX_TAGS]
        doc_ids = idx.ids()
        course_ids = set()
        for doc_id in doc_ids:
            obj = intids.queryObject(doc_id)
            if obj is None or ICourseInstance.providedBy(obj):
                course_ids.add(doc_id)
        for remove_id in course_ids:
            idx.unindex_doc(remove_id)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done (unindexed_count=%s)', generation, len(course_ids))


def evolve(context):
    """
    Evolve to generation 45 by removing courses from the tag index.
    """
    do_evolve(context, generation)

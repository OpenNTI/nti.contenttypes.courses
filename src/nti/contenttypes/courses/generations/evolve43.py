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

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.index import IX_COURSE_INSTRUCTOR
from nti.contenttypes.courses.index import IX_COURSE_EDITOR
from nti.contenttypes.courses.index import InstructorSetIndex
from nti.contenttypes.courses.index import EditorSetIndex
from nti.contenttypes.courses.index import install_courses_catalog


from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

generation = 43

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


def index_courses(index, course_catalog, intids, seen):
    for entry in course_catalog.iterCatalogEntries():
        course = ICourseInstance(entry, None)
        doc_id = intids.queryId(course)
        if doc_id is None or doc_id in seen:
            continue
        seen.add(doc_id)
        index.index_doc(doc_id, course)


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
        for name, clazz in ((IX_COURSE_INSTRUCTOR, InstructorSetIndex),
                            (IX_COURSE_EDITOR, EditorSetIndex)):
            if name not in catalog:
                index = clazz(family=intids.family)
                intids.register(index)
                locate(index, catalog, name)
                catalog[name] = index

        seen = set()
        for site in get_all_host_sites():
            with current_site(site):
                course_catalog = component.queryUtility(ICourseCatalog)
                if course_catalog is not None:
                    index_courses(catalog, course_catalog, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done', generation)


def evolve(context):
    """
    Evolve to generation 43 by adding instructors/editors indexes to courses catalog.
    """
    do_evolve(context, generation)

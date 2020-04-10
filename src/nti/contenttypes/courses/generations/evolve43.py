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

from nti.contenttypes.courses.index import IX_INSTRUCTORS
from nti.contenttypes.courses.index import IX_EDITORS
from nti.contenttypes.courses.index import InstructorSetIndex
from nti.contenttypes.courses.index import EditorSetIndex
from nti.contenttypes.courses.index import install_enrollment_catalog

from nti.contenttypes.courses.utils import index_course_editors
from nti.contenttypes.courses.utils import index_course_instructors

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

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

        enrollment_catalog = install_enrollment_catalog(ds_folder, intids)
        for name, clazz in ((IX_INSTRUCTORS, InstructorSetIndex),
                            (IX_EDITORS, EditorSetIndex)):
            if name not in enrollment_catalog:
                index = clazz(family=intids.family)
                intids.register(index)
                locate(index, enrollment_catalog, name)
                enrollment_catalog[name] = index

        seen = set()
        for site in get_all_host_sites():
            with current_site(site):
                catalog = component.queryUtility(ICourseCatalog)
                if catalog is None or catalog.isEmpty():
                    continue

                for entry in catalog.iterCatalogEntries():
                    course = ICourseInstance(entry, None)
                    doc_id = intids.queryId(course)
                    if doc_id is None or doc_id in seen:
                        continue
                    seen.add(doc_id)

                    index_course_editors(course, enrollment_catalog, entry, doc_id)
                    index_course_instructors(course, enrollment_catalog, entry, doc_id)

        total_editors = enrollment_catalog[IX_EDITORS].wordCount()
        total_instructors = enrollment_catalog[IX_INSTRUCTORS].wordCount()

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done, total editors: %s, total instructors: %s.',
                generation,
                total_editors,
                total_instructors)


def evolve(context):
    """
    Evolve to generation 43 by adding instructors/editors indexes to enrollment catalog.
    """
    do_evolve(context, generation)

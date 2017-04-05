#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 29

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.index import IX_ENTRY
from nti.contenttypes.courses.index import IX_CREATEDTIME
from nti.contenttypes.courses.index import IX_LASTMODIFIED
from nti.contenttypes.courses.index import RecordCreatedTimeIndex
from nti.contenttypes.courses.index import RecordLastModifiedIndex
from nti.contenttypes.courses.index import install_enrollment_catalog

from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver


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
        
        catalog = install_enrollment_catalog(ds_folder, intids)
        for name, clazz in ((IX_CREATEDTIME, RecordCreatedTimeIndex),
                            (IX_LASTMODIFIED, RecordLastModifiedIndex)):
            if name not in catalog:
                index = clazz(family=intids.family)
                intids.register(index)
                locate(index, catalog, name)
                catalog[name] = index
        index = catalog[IX_ENTRY]
        for doc_id in list(index.ids()): # mutating
            obj = intids.queryObject(doc_id)
            if ICourseInstanceEnrollmentRecord.providedBy(obj):
                catalog.index_doc(doc_id, obj)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 29 by adding created/lastMod indexes to enrollment catalog
    """
    do_evolve(context, generation)

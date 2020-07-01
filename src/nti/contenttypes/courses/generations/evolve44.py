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

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.metadata.index import get_metadata_catalog

from nti.dataserver.users.index import get_entity_catalog

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.site.hostpolicy import get_all_host_sites

generation = 44

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


def update_scope_name(scope, doc_id, course_title, catalogs):
    friendly_named = IFriendlyNamed(scope, None)
    if     friendly_named is None \
        or friendly_named.realname:
        logger.info("Scope already has realname (%s) (%s) (%s)",
                    scope.__name__, scope.NTIID, friendly_named.realname)
        return

    scope_name = scope.__name__
    new_name = course_title if scope_name == ES_PUBLIC else '%s (%s)' % (course_title, scope_name)
    friendly_named.realname = new_name
    for catalog in catalogs:
        catalog.index_doc(doc_id, scope)


def process_course(course, intids):
    entry = ICourseCatalogEntry(course, None)
    course_title = getattr(entry, 'title', None)
    if not course_title:
        return
    scopes = course.SharingScopes
    catalogs = (get_metadata_catalog(), get_entity_catalog())
    for scope in scopes.values():
        doc_id = intids.queryId(scope)
        if doc_id is not None:
            update_scope_name(scope, doc_id, course_title, catalogs)


def process_site(intids, seen):
    course_catalog = component.queryUtility(ICourseCatalog)
    if course_catalog and not course_catalog.isEmpty():
        for entry in course_catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            process_course(course, intids)


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
        for site in get_all_host_sites():
            with current_site(site):
                process_site(intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 44 by updating the scopes realname to reflect the course
    title.
    """
    do_evolve(context, generation)

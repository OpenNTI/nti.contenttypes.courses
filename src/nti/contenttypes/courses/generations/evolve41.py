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

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceBoard
from nti.contenttypes.courses.interfaces import ICourseInstanceForum

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver
from nti.dataserver.interfaces import IACLProvider

from nti.site.hostpolicy import get_all_host_sites

logger = __import__('logging').getLogger(__name__)

generation = 41


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
    logger.info('Processing course %s ', course.ntiid)
    discussions = course.Discussions
    if not ICourseInstanceBoard.providedBy(discussions):
        logger.warn('Skipping course %s because discussions are not ICourseInstanceBoard. Legacy Course?', discussions.NTIID)
        return

    for forum in discussions.values():
        if not ICourseInstanceForum.providedBy(forum):
            logger.debug('Marking %s as ICourseInstanceForum', forum.NTIID)
            interface.alsoProvides(forum, ICourseInstanceForum)
        if IACLProvider.providedBy(forum) and getattr(forum, '__acl__', None):
            logger.debug('Marking %s as no longer providing IACLProvider', forum.NTIID)
            interface.noLongerProvides(forum, IACLProvider)
            if hasattr(forum, '__acl__'):
                logger.debug('Removing legacy __acl__ for %s', forum.NTIID)
                forum.__legacy__acl__ = forum.__acl__
                del forum.__acl__
            


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
            process_course(course)


def do_evolve(context, generation=generation):
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
        logger.info('Evolution %s started.', generation)
        for current_site in get_all_host_sites():
            _process_site(current_site, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done', generation)


def evolve(context):
    """
    Evolve to 41 by making sure forums in course discussions have proper
    acls. This migration ensures that all forums in an ICourseInstanceBoard
    now implement some varient of ICourseInstanceForum (now handled via an
    object added subscriber) and it removes the use of pickled `__acl__`s on such
    forums by making them no longer provide `IACLProvider`.  The existing persistent
    `__acl__` and `__entities__` attributes are left in place for now.
    """
    do_evolve(context, generation)

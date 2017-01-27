#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 25

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.index import IX_COURSE

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.index import install_enrollment_catalog

from nti.dataserver.interfaces import IUser
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


def remove_from_container(container, key, event=False):
    # XXX. Avoid throwing intIdRemovedEvent (analytics tries to store in redis).
    container._delitemf(key, event=event)
    try:
        container.updateLastMod()
    except AttributeError:
        pass
    container._p_changed = True


def unenroll(record, principal_id):
    try:
        course = record.CourseInstance
        enrollment_manager = ICourseEnrollmentManager(course)
        remove_from_container(enrollment_manager._cat_enrollment_storage, 
                              principal_id)
        remove_from_container(enrollment_manager._inst_enrollment_storage,
                              principal_id)
    except (TypeError, KeyError):
        pass


def _clean_up_enrollments(site_name, enroll_catalog, intids, seen, course_catalog):
    for entry in course_catalog.iterCatalogEntries():
        if entry.ntiid in seen:
            continue
        seen.add(entry.ntiid)
        course = ICourseInstance(entry, None)
        if course is not None:
            # Get enrollment records for course
            query = {IX_COURSE: {'any_of': (entry.ntiid,)}, }
            for record_id in enroll_catalog.apply(query) or ():
                record = intids.queryObject(record_id)
                if ICourseInstanceEnrollmentRecord.providedBy(record):
                    if IUser(record, None) is None:
                        # If we have no user, remove the record and unenroll;
                        # this is invalid state.
                        # Get our weak_ref principal name.
                        principal = record._principal.username
                        logger.info("[%s] Removing enrollment record for (user=%s) (entry=%s)",
                                    site_name, principal, entry.ntiid)
                        unenroll(record, principal)
                        enroll_catalog.unindex_doc(record_id)


def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert  component.getSiteManager() == ds_folder.getSiteManager(), \
                "Hooks not installed?"
        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        enroll_catalog = install_enrollment_catalog(ds_folder, intids)

        seen = set()
        for site in get_all_host_sites():
            with current_site(site):
                course_catalog = component.queryUtility(ICourseCatalog)
                if course_catalog is not None:
                    site_name = site.__name__
                    _clean_up_enrollments(site_name, enroll_catalog,
                                          intids, seen, course_catalog)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 25 by removing enrollment records without a valid user.
    """
    do_evolve(context, generation)

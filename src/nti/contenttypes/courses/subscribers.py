#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Event listeners.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.component.hooks import site

from zope.intid import IIntIds

from zope.interface.interfaces import IRegistered
from zope.interface.interfaces import IUnregistered

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IPersistentContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageLibraryDidSyncEvent
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

from nti.site.localutility import install_utility
from nti.site.localutility import uninstall_utility_on_unregistration

from nti.site.site import get_component_hierarchy_names

from .catalog import CourseCatalogFolder

from .index import IX_COURSE, IX_SCOPE, IX_SITE

from .interfaces import INSTRUCTOR
from .interfaces import iface_of_node

from .interfaces import ICourseOutline
from .interfaces import ICourseInstance
from .interfaces import ICourseOutlineNode
from .interfaces import ICourseCatalogEntry
from .interfaces import IObjectEntrySynchronizer
from .interfaces import IPersistentCourseCatalog
from .interfaces import ICourseRolesSynchronized

from .utils import index_course_instructors

from . import get_enrollment_catalog

COURSE_CATALOG_NAME = 'Courses'

# XXX: This is very similar to nti.contentlibrary.subscribers

@component.adapter(IPersistentContentPackageLibrary, IRegistered)
def install_site_course_catalog(local_library, _=None):
	"""
	When a new local site, representing a site (host) policy
	is added, install a site-local course-catalog and associated utilities
	into it. The catalog is sync'd after this is done.

	If you need to perform work, such as registering your own
	utility in the local site that uses the local catalog, listen for the component
	registration event, :class:`zope.interface.interfaces.IRegistered`,
	which is an ObjectEvent, whose object will be an
	:class:`nti.contenttypes.courses.interfaces.IPersistentCourseCatalog`.

	Although this function is ordinarily called as an event listener
	for a :class:`.IRegistered` event for a
	:class:`.IPersistentContentPackageLibrary`, it can also be called
	manually, passing in just a site manager. In that case, if there
	is no local course catalog, and one can now be found, it will be
	created; if a local catalog already exists, nothing will be done.

	:returns: The site local catalog, if one was found or installed.
	"""

	# We take either a local library, which will be in the context
	# of a site manager, or the site manager itself, which
	# is directly adaptable to IComponentLookup
	# (zope.component.hooks tries to adapt context to IComponentLookup,
	# and zope.site.site contains a SiteManagerAdapter that walks
	# up the parent tree)
	local_site_manager = component.getSiteManager(local_library)

	if _ is None and COURSE_CATALOG_NAME in local_site_manager:
		cat = local_site_manager[COURSE_CATALOG_NAME]
		logger.debug("Nothing to do for site %s, catalog already present %s",
					 local_site_manager, cat)
		return cat

	local_site = local_site_manager.__parent__
	assert bool(local_site.__name__), "sites must be named"

	catalog = CourseCatalogFolder()

	with site(local_site):
		# install in this site so the right utilities and event
		# listeners are found
		# Before we install (which fires a registration event that things might
		# be listening for) set up the dependent utilities
		install_utility(catalog,
						COURSE_CATALOG_NAME,
						IPersistentCourseCatalog,
						local_site_manager)

		# Note that it is not safe to sync if we got here as the result
		# of the registration event...that can lead to cycles,
		# because the library syncs itself on registration. wait for
		# that event.
		if _ is None:
			if not IPersistentContentPackageLibrary.providedBy(local_library):
				# because we cold have been handed the site
				local_library = local_site_manager.getUtility(IContentPackageLibrary)
			sync_catalog_when_library_synched(local_library, None)
		return catalog

@component.adapter(IPersistentContentPackageLibrary, IUnregistered)
def uninstall_site_course_catalog(library, event):
	uninstall_utility_on_unregistration(COURSE_CATALOG_NAME,
										IPersistentCourseCatalog,
										event)

# Sync-related subscribers

@component.adapter(IPersistentContentPackageLibrary, IContentPackageLibraryDidSyncEvent)
def sync_catalog_when_library_synched(library, event):
	"""
	When a persistent content library is synchronized
	with the disk contents, whether or not anything actually changed,
	we also synchronize the corresponding course catalog. (Because they could
	change independently and in unknown ways)
	"""

	# sync params/results
	params = event.params
	results = event.results

	# Find the local site manager
	site_manager = component.getSiteManager(library)
	if library.__parent__ is not site_manager:
		logger.warn("Expected to find persistent library in its own site; refusing to sync")
		return

	catalog = site_manager.get(COURSE_CATALOG_NAME)
	if catalog is None:
		logger.info("Installing and synchronizing course catalog for %s", site_manager)
		# which in turn will call back to us
		install_site_course_catalog(library)
		return

	enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
	enumeration_root = enumeration.root
	courses_bucket = enumeration_root.getChildNamed(catalog.__name__)
	if courses_bucket is None:
		logger.info("Not synchronizing: no directory named %s in %s for catalog %s",
					catalog.__name__,
					getattr(enumeration_root, 'absolute_path', enumeration_root),
					catalog)
		return

	logger.info("Synchronizing course catalog %s in site %s from directory %s",
				 catalog, site_manager.__parent__.__name__,
				 getattr(courses_bucket, 'absolute_path', courses_bucket))

	synchronizer = component.getMultiAdapter((catalog, courses_bucket),
							   				  IObjectEntrySynchronizer)
	synchronizer.synchronize(catalog, courses_bucket, params=params, results=results)

@component.adapter(ICourseInstance, ICourseRolesSynchronized)
def roles_sync_on_course_instance(course, event):
	catalog = get_enrollment_catalog()
	intids = component.queryUtility(IIntIds)
	if catalog is None or intids is None:
		return
	entry = ICourseCatalogEntry(course, None)
	ntiid = getattr(entry, 'ntiid', None)
	if ntiid:  # remove all instructors
		sites = get_component_hierarchy_names()
		query = { IX_SITE: {'any_of':sites},
				  IX_COURSE: {'any_of':(ntiid,)},
				  IX_SCOPE : {'any_of':(INSTRUCTOR,)}}
		for uid in catalog.apply(query) or ():
			catalog.unindex_doc(uid)

	# reindex
	index_course_instructors(course, catalog=catalog, intids=intids)

@component.adapter(ICourseInstance, IObjectRemovedEvent)
def on_course_instance_removed(course, event):
	catalog = get_enrollment_catalog()
	entry = ICourseCatalogEntry(course, None)
	ntiid = getattr(entry, 'ntiid', None)
	if catalog is None or not ntiid:
		return

	query = { IX_COURSE: {'any_of':(ntiid,)} }
	for uid in catalog.apply(query) or ():
		catalog.unindex_doc(uid)

@component.adapter(ICourseOutlineNode, IObjectAddedEvent)
def on_outline_node_added(node, event):
	if ICourseOutline.providedBy(node):
		return
	try:
		provided = iface_of_node(node)
		registry = component.getSiteManager()
		registerUtility(registry,
						component=node,
						provided=provided,
						name=node.ntiid)
	except AttributeError:
		pass

@component.adapter(ICourseOutlineNode, IObjectRemovedEvent)
def on_outline_node_removed(node, event):
	if ICourseOutline.providedBy(node):
		return
	try:
		provided = iface_of_node(node)
		registry = component.getSiteManager()
		unregisterUtility(registry, provided=provided, name=node.ntiid)
	except AttributeError:
		pass

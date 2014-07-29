#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementations of enrollment related structures and utilities.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope.interface import ro
from zope import component
from zope import lifecycleevent
from zope.annotation.factory import factory as an_factory
from ZODB.interfaces import IConnection

from nti.wref.interfaces import IWeakRef

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.schema.schema import SchemaConfigured

from zope.container.interfaces import IContainer
from zope.container.interfaces import IContained
from zope.container.constraints import contains

from zope.security.interfaces import IPrincipal

from .interfaces import ICourseInstanceEnrollmentRecord
from .interfaces import ICourseEnrollmentManager
from .interfaces import ICourseEnrollments
from .interfaces import ICourseInstance
from .interfaces import ICourseCatalog
from .interfaces import IGlobalCourseCatalog
from .interfaces import ES_PUBLIC
from .interfaces import ES_CREDIT
from .interfaces import IPrincipalEnrollments

from nti.contentlibrary.bundle import _readCurrent
from nti.utils.property import alias
from nti.utils.property import Lazy
from zope.cachedescriptors.method import cachedIn

from nti.schema.fieldproperty import FieldProperty

class IDefaultCourseInstanceEnrollmentStorage(IContainer,IContained):
	"""
	Maps from principal ids to their enrollment record.
	"""
	contains(ICourseInstanceEnrollmentRecord)

class IDefaultCourseCatalogEnrollmentStorage(IContainer,IContained):
	"""
	Maps from principal IDs to a persistent list of their
	enrollments.
	"""

	def enrollments_for_id(principalid, principal):
		"""
		Return the persistent list to hold weak references for
		the principal.

		:param principal: If this has a non-None `_p_jar`, the enrollment
			list will be stored in this jar.
		"""

from nti.dataserver.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer
from persistent.list import PersistentList

# Recall that everything that's keyed by username/principalid must be case-insensitive

@component.adapter(ICourseInstance)
@interface.implementer(IDefaultCourseInstanceEnrollmentStorage)
class DefaultCourseInstanceEnrollmentStorage(CaseInsensitiveCheckingLastModifiedBTreeContainer):
	pass

DefaultCourseInstanceEnrollmentStorageFactory = an_factory(DefaultCourseInstanceEnrollmentStorage,
														   'CourseInstanceEnrollmentStorage')

@interface.implementer(IContained)
class CourseEnrollmentList(PersistentList):
	__name__ = None
	__parent__ = None

@component.adapter(ICourseCatalog)
@interface.implementer(IDefaultCourseCatalogEnrollmentStorage)
class DefaultCourseCatalogEnrollmentStorage(CaseInsensitiveCheckingLastModifiedBTreeContainer):
	__name__ = None
	__parent__ = None

	def enrollments_for_id(self, principalid, principal):
		try:
			return _readCurrent(self[principalid])
		except KeyError:
			result = CourseEnrollmentList()
			jar = IConnection(principal, None)
			if jar is not None:
				jar.add(result)

			self[principalid] = result
			return result

DefaultCourseCatalogEnrollmentStorageFactory = an_factory(DefaultCourseCatalogEnrollmentStorage,
														  'CourseCatalogEnrollmentStorage')

class GlobalCourseCatalogEnrollmentStorage(DefaultCourseCatalogEnrollmentStorage):
	pass

@component.adapter(IGlobalCourseCatalog)
@interface.implementer(IDefaultCourseCatalogEnrollmentStorage)
def global_course_catalog_enrollment_storage(catalog):
	"""
	Global course catalogs are not persisted in the database,
	so we have to find somewhere else to put them.

	When we are called, our current site should be a persistent
	site in the database, so we store things there.
	"""

	site_manager = component.getSiteManager()
	try:
		return site_manager['default']['GlobalCourseCatalogEnrollmentStorage']
	except KeyError:
		storage = GlobalCourseCatalogEnrollmentStorage()
		site_manager['default']['GlobalCourseCatalogEnrollmentStorage'] = storage
		# This could be reachable from a few different databases
		# (because records which are children live with their
		# principal's database), so give it a home
		jar = IConnection(storage, None)
		if jar is not None:
			jar.add(storage)
		return storage

def _global_course_catalog_storage(site_manager):
	"""
	Returns a storage if it exists in the given site manager, otherwise
	returns nothing.
	"""
	try:
		return site_manager['default']['GlobalCourseCatalogEnrollmentStorage']
	except (KeyError, TypeError):
		return None


@component.adapter(ICourseInstance)
@interface.implementer(ICourseEnrollmentManager)
class DefaultCourseEnrollmentManager(object):
	"""
	The default enrollment manager.

	To be able to efficiently answer questions both starting
	from the course and starting from the principal, we
	store enrollment records directly as an annotation on the course,
	and use the enclosing course catalog entry to store
	a map describing which principals *might* have entries
	in which courses.
	"""

	def __init__(self, context, request=None):
		self.context = context
		self.request = request

	_course = alias('context')

	# all of these accesses do _readCurrent, because we are
	# modifying a set of related objects based on the contents
	# of one of them

	@Lazy
	def _inst_enrollment_storage(self):
		storage = IDefaultCourseInstanceEnrollmentStorage(self._course)
		if storage._p_jar is None:
			jar = IConnection(storage, None)
			if jar is not None:
				jar.add(storage)
		return _readCurrent(storage)

	@Lazy
	def _catalog(self):
		try:
			return component.getUtility(ICourseCatalog, context=self._course)
		except LookupError:
			# Course must be unanchored and/or in the global site?
			# we only expect this is in tests (legacy cases use their
			# own manager)
			return component.getUtility(ICourseCatalog)

	@Lazy
	def _cat_enrollment_storage(self):
		return _readCurrent(IDefaultCourseCatalogEnrollmentStorage(self._catalog))

	###
	# NOTE: The enroll/drop methods DO NOT set up any of the scope
	# information; that's left to ObjectEvent subscribers. That may
	# seem like action at a distance, but the rationale is that we
	# want to, in addition to the Added and Removed events fired here,
	# support Modified events (e.g., a user starts out open/public
	# enrolled, then pays for the course, and becomes for-credit-non-degree)
	###

	def enroll(self, principal, scope=ES_PUBLIC):
		principal_id = IPrincipal(principal).id
		if principal_id in self._inst_enrollment_storage:
			return False

		record = DefaultCourseInstanceEnrollmentRecord(Principal=principal, Scope=scope)
		enrollments = _readCurrent(self._cat_enrollment_storage.enrollments_for_id(principal_id,
																				   principal))

		lifecycleevent.created(record)
		enrollments.append(record)
		try:
			enrollments._p_jar.add(record)
		except AttributeError:
			pass
		# now install and fire the ObjectAdded event, after
		# it's in the IPrincipalEnrollments; that way
		# event listeners will see consistent data.
		self._inst_enrollment_storage[principal_id] = record

		return record

	def drop(self, principal):
		principal_id = IPrincipal(principal).id
		if principal_id not in self._inst_enrollment_storage:
			return False

		record = self._inst_enrollment_storage[principal_id]
		# again be consistent with the order: remove from the
		# enrollment list then fire the event
		enrollments = _readCurrent(self._cat_enrollment_storage.enrollments_for_id(principal_id,
																				   principal))
		try:
			record_ix = enrollments.index(record)
			del enrollments[record_ix]
		except ValueError:
			# Snap, the enrollment is missing from the course catalog storage of the
			# principal, but we have it in the course instance storage.
			# This is probably that migration problem, so look up the tree to see
			# if we can find the record.
			# FIXME: Unittests for this code path
			for site_manager in ro.ro(component.getSiteManager()):
				storage = _global_course_catalog_storage(site_manager)
				if storage is not None and principal_id in storage:
					_readCurrent(storage)
					enrollments = _readCurrent(storage.enrollments_for_id(principal_id, principal))
					try:
						record_ix = enrollments.index(record)
						del enrollments[record_ix]
						break
					except ValueError:
						pass

		del self._inst_enrollment_storage[principal_id]

		return record

from nti.dataserver.interfaces import ILengthEnumerableEntityContainer

@component.adapter(ICourseInstance)
@interface.implementer(ICourseEnrollments)
class DefaultCourseEnrollments(object):

	def __init__(self, context):
		self.context = context

	@Lazy
	def _inst_enrollment_storage(self):
		storage = IDefaultCourseInstanceEnrollmentStorage(self._course)
		if storage._p_jar is None:
			jar = IConnection(storage, None)
			if jar is not None:
				jar.add(storage)
		return _readCurrent(storage)

	def iter_enrollments(self):
		return self._inst_enrollment_storage.values()

	def count_enrollments(self):
		return len(self._inst_enrollment_storage)

	def get_enrollment_for_principal(self, principal):
		principal_id = IPrincipal(principal).id
		return self._inst_enrollment_storage.get(principal_id)

	# Non-interface methods for legacy compatibility
	def count_legacy_forcredit_enrollments(self):
		return len(ILengthEnumerableEntityContainer(self.context.SharingScopes[ES_CREDIT]))

	@cachedIn('_v_count_open_enrollments')
	def count_legacy_open_enrollments(self):
		# XXX: Inefficient but accurate
		i = 0
		for x in self.iter_enrollments():
			if x.Scope == ES_PUBLIC:
				i += 1
		return i


@interface.implementer(IPrincipalEnrollments)
class DefaultPrincipalEnrollments(object):

	def __init__(self, principal):
		self.principal = principal

	def iter_enrollments(self):
		iprincipal = IPrincipal(self.principal, None)
		if iprincipal is None:
			return

		principal_id = iprincipal.id
		# See comments in catalog.py about queryNextUtility
		catalogs = reversed(component.getAllUtilitiesRegisteredFor(ICourseCatalog))
		seen_cats = []
		seen_storages = []
		seen_records = []

		for catalog in catalogs:
			# Protect against accidentally hitting the same catalog
			# or record multiple times. This can occur (only during tests)
			# if the component registry is manually dorked with. The same storage,
			# however, may be seen multiple times as we walk back up the resolution tree
			if catalog in seen_cats:
				continue
			seen_cats.append(catalog)
			storage = IDefaultCourseCatalogEnrollmentStorage(catalog)
			if storage in seen_storages:
				continue
			seen_storages.append(storage)

		# Now, during migration, we may have put things in a global storage
		# that is not our current global storage. One example:
		# we migrate with the current site platform.ou.edu, but query with the
		# current site janux.ou.edu. Therefore we need to walk up the chain of these
		# guys too. This is not the most elegant approach, but it does work.
		for site_manager in ro.ro(component.getSiteManager()):
			storage = _global_course_catalog_storage(site_manager)
			if storage in seen_storages:
				continue
			seen_storages.append(storage)

		for storage in seen_storages:
			if storage is None:
				continue

			if principal_id in storage:
				for i in storage.enrollments_for_id(principal_id, self.principal):
					if i in seen_records:
						continue
					seen_records.append(i)

					yield i

from nti.dataserver.interfaces import IUser

@interface.implementer(ICourseInstanceEnrollmentRecord)
class DefaultCourseInstanceEnrollmentRecord(SchemaConfigured,
											PersistentCreatedAndModifiedTimeObject):
	"""
	Persistent implementation of a enrollment record.

	We are only used in DefaultEnrollmentManagers because we expect
	to know how we are stored.
	"""

	__parent__ = None
	__name__ = None

	Scope = FieldProperty(ICourseInstanceEnrollmentRecord['Scope'])

	def __init__(self, **kwargs):
		PersistentCreatedAndModifiedTimeObject.__init__(self)
		SchemaConfigured.__init__(self, **kwargs)

	def _get_CourseInstance(self):
		"""
		We know we are stored as a child of an annotation of a course.
		"""
		try:
			return self.__parent__.__parent__
		except AttributeError:
			return None

	CourseInstance = property(_get_CourseInstance, lambda s, nv: None)

	_principal = None
	def _get_Principal(self):
		return self._principal() if self._principal is not None else None

	def _set_Principal(self, nv):
		if nv is None:
			if self._principal is not None:
				del self._principal
		else:
			self._principal = IWeakRef(nv)

	Principal = property(_get_Principal, _set_Principal)

	def __eq__(self, other):
		try:
			return self is other or (self.__name__, self.__parent__) == (other.__name__, other.__parent__)
		except AttributeError:
			return NotImplemented

	def _ne__(self, other):
		try:
			return self is not other and (self.__name__, self.__parent__) != (other.__name__, other.__parent__)
		except AttributeError:
			return NotImplemented

	def __conform__(self, iface):
		if ICourseInstance.isOrExtends(iface):
			return self.CourseInstance

		if IPrincipal.isOrExtends(iface):
			return self.Principal

		if IUser.isOrExtends(iface):
			return self.Principal

# Subscribers to keep things in sync when
# objects are deleted.
# We may have intid-weak references to these things,
# so we need to catch them on the IntIdRemoved event
# for dependable ordering


def on_principal_deletion_unenroll(principal, event):
	pins = component.subscribers( (principal,), IPrincipalEnrollments )
	for enrollments in pins:

		for record in enrollments.iter_enrollments():
			course = record.CourseInstance
			manager = ICourseEnrollmentManager(course)
			manager.drop(principal)

def on_course_deletion_unenroll(course, event):
	enrollments = ICourseEnrollments(course)
	manager = ICourseEnrollmentManager(course)
	for record in enrollments.iter_enrollments():
		principal = record.Principal
		manager.drop(principal)

	# XXX: In the future, depending on how we go with Sections
	# and having a "master" scope in the  parent section,
	# this could also require us checking through the parents
	# if it was a sub-instance that got deleted

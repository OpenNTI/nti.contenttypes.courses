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
from .interfaces import ES_PUBLIC
from .interfaces import IPrincipalEnrollments

from nti.contentlibrary.bundle import _readCurrent
from nti.utils.property import alias
from nti.utils.property import Lazy

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
		return _readCurrent(IDefaultCourseInstanceEnrollmentStorage(self._course))

	@Lazy
	def _catalog(self):
		try:
			return component.getNextUtility(self._course, ICourseCatalog)
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
		lifecycleevent.created(record)
		# now install and fire the ObjectAdded event
		self._inst_enrollment_storage[principal_id] = record

		enrollments = _readCurrent(self._cat_enrollment_storage.enrollments_for_id(principal_id,
																				   principal))

		enrollments.append(record)

		return record

	def drop(self, principal):
		principal_id = IPrincipal(principal).id
		if principal_id not in self._inst_enrollment_storage:
			return False

		record = self._inst_enrollment_storage[principal_id]
		# reverse the order: remove from the enrollment list
		# then fire the event

		enrollments = _readCurrent(self._cat_enrollment_storage.enrollments_for_id(principal_id,
																				   principal))
		record_ix = enrollments.index(record)
		del enrollments[record_ix]

		del self._inst_enrollment_storage[principal_id]
		return record

@component.adapter(ICourseInstance)
@interface.implementer(ICourseEnrollments)
class DefaultCourseEnrollments(object):

	def __init__(self, context):
		self.context = context

	@Lazy
	def _inst_enrollment_storage(self):
		return IDefaultCourseInstanceEnrollmentStorage(self.context)

	def iter_enrollments(self):
		return self._inst_enrollment_storage.values()

	def count_enrollments(self):
		return len(self._inst_enrollment_storage)

@interface.implementer(IPrincipalEnrollments)
class DefaultPrincipalEnrollments(object):

	def __init__(self, principal):
		self.principal = principal

	def iter_enrollments(self):
		principal_id = IPrincipal(self.principal).id
		catalog = component.queryUtility(ICourseCatalog)
		while catalog is not None:
			storage = IDefaultCourseCatalogEnrollmentStorage(catalog)
			if principal_id in storage:
				for i in storage.enrollments_for_id(principal_id, self.principal):
					yield i
			catalog = component.queryNextUtility(catalog, ICourseCatalog)


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

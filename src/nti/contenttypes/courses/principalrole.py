#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Custom implementations  of the principal role map for the objects
defined in this package.

The possible roles are defined in ZCML.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from .interfaces import ICourseInstance
from .interfaces import RID_TA
from .interfaces import RID_INSTRUCTOR

from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import Unset

@interface.implementer(IPrincipalRoleMap)
@component.adapter(ICourseInstance)
class CourseInstancePrincipalRoleMap(object):

	def __init__(self, course):
		self.context = course

	_SUPPORTED_ROLES = (RID_TA, RID_INSTRUCTOR)

	def _principals_for_ta(self):
		# XXX: FIXME: Right now, we don't have anything that distinguishes
		# the TAs from the instructors definitevely. All we have is the catalog
		# entry and the convention that the JobTitle will be 'Teaching Assistant'
		# So right now we never put anyone in that role.
		return ()

	def _principals_for_instructor(self):
		# Therefore everything left is an instructor, and
		# for the moment we say that everyone is an instructor
		return self.context.instructors

	@property
	def __role_meth(self):
		# Order might matter. Query instructors first
		return ((RID_INSTRUCTOR, self._principals_for_instructor),
				(RID_TA, self._principals_for_ta))


	def getPrincipalsForRole(self, role_id):
		role_meth = dict(self.__role_meth)
		if role_id not in role_meth:
			return []

		return [(x.id, Allow) for x in role_meth[role_id]()]

	def getRolesForPrincipal(self, principal_id):
		for rid, meth in self.__role_meth:
			if principal_id in [x.id for x in meth()]:
				return [(rid, Allow)]
		return []

	def getSetting(self, role_id, principal_id, default=Unset):
		if role_id not in self._SUPPORTED_ROLES:
			return default

		for rid, setting in self.getRolesForPrincipal(principal_id):
			if role_id == rid:
				return setting

		return default

	def getPrincipalsAndRoles(self):
		result = []
		for rid, meth in self.__role_meth:
			result.extend( ((rid, x.id, Allow) for x in meth()))
		return result

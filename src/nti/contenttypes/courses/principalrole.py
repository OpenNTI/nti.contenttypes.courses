#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Custom implementations  of the principal role map for the objects
defined in this package.

The possible roles are defined in ZCML.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import Unset
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from zope.securitypolicy.rolepermission import AnnotationRolePermissionManager

from nti.dataserver.authorization import ACT_PIN
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseRolePermissionManager

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(IPrincipalRoleMap)
class CourseInstancePrincipalRoleMap(object):

    _SUPPORTED_ROLES = (RID_TA, RID_INSTRUCTOR)

    def __init__(self, course):
        self.context = course

    def _principals_for_ta(self):
        # Right now, we don't have anything that distinguishes
        # the TAs from the instructors definitively. All we have is the catalog
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
            return ()
        return [(x.id, Allow) for x in role_meth[role_id]()]

    def getRolesForPrincipal(self, principal_id):
        for rid, meth in self.__role_meth:
            if principal_id in [x.id for x in meth()]:
                return [(rid, Allow)]
        return ()

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
            result.extend(((rid, x.id, Allow) for x in meth()))
        return result


@component.adapter(ICourseInstance)
@interface.implementer(ICourseRolePermissionManager)
class CourseRolePermissionManager(AnnotationRolePermissionManager):

    def initialize(self):
        if not self.map or not self.map._byrow:  # pylint: disable=protected-access
            # Initialize with perms for our global content admin.
            for perm in (ACT_READ, ACT_CONTENT_EDIT, ACT_UPDATE):
                self.grantPermissionToRole(perm.id, ROLE_CONTENT_ADMIN.id)

            # Initialize with perms for NT admins, site admins will pick up
            # access via the site.
            for permission in (ACT_READ,):
                self.grantPermissionToRole(permission.id, ROLE_ADMIN.id)

    def getRolesForPermission(self, perm):
        #: Ensure our instructors/TAs have PIN access under this context
        result = super(CourseRolePermissionManager, self).getRolesForPermission(perm)
        if perm == ACT_PIN.id:
            for role_id in (RID_INSTRUCTOR, RID_TA):
                result.append((role_id, Allow))
        return result

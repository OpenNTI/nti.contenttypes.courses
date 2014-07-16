#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reads the instructor role grants and synchronizes them.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.securitypolicy.interfaces import IPrincipalRoleManager
from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.role import checkRole
from zope.securitypolicy.securitymap import PersistentSecurityMap

from .interfaces import RID_INSTRUCTOR
from zope.security.interfaces import IPrincipal

def _fill_roles_from_json(course, manager, json):
	"""
	A json dict that looks like::

	    {'role_id':
	         {
	          'allow': ['p1', 'p2'],
	           'deny':  ['p3', 'p4']
	         },
	     ... }

	"""

	for role_id, role_values in json.items():
		checkRole(course, role_id)

		allows = role_values.get('allow', ())
		for principal_id in allows:
			manager.assignRoleToPrincipal(role_id, principal_id)

		denies = role_values.get('deny', ())
		for principal_id in denies:
			manager.removeRoleFromPrincipal(role_id, principal_id)

def reset_roles_missing_key(course):
	role_manager = IPrincipalRoleManager(course)
	# We totally cheat here and clear the role manager.
	# this is much easier than trying to actually sync
	# it
	if isinstance(role_manager.map, PersistentSecurityMap):
		role_manager.map._byrow.clear()
		role_manager.map._bycol.clear()
		role_manager.map._p_changed = True


def fill_roles_from_key(course, key):
	"""
	XXX Fill in description

	Unlike that function, this function does set the last modified
	time to the time of that key (and sets the root of the catalog entry to
	the key). It also only does anything if the modified time has
	changed.

	:return: The entry
	"""

	# RoleManagers are not required to have lastModified by default...

	role_manager = IPrincipalRoleManager(course)
	role_last_mod = getattr(role_manager, 'lastModified', 0)

	if key.lastModified <= role_last_mod:
		return role_manager

	reset_roles_missing_key(role_manager)

	json = key.readContentsAsJson()
	_fill_roles_from_json(course, role_manager, json)
	role_manager.lastModified = key.lastModified

	# For BWC, we update the instructor list too
	course.instructors = tuple([IPrincipal(x[0])
								for x in
								role_manager.getPrincipalsForRole(RID_INSTRUCTOR)
								if x[1] is Allow])

	return role_manager

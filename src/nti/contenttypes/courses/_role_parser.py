#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reads the instructor role grants and synchronizes them.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.intid

from zope import component

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.role import checkRole
from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleManager
from zope.securitypolicy.securitymap import PersistentSecurityMap

from ZODB.interfaces import IConnection

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.dataserver.users import User
from nti.dataserver.interfaces import IUser

from .interfaces import RID_TA
from .interfaces import RID_INSTRUCTOR

from .sharing import add_principal_to_course_content_roles
from .sharing import remove_principal_from_course_content_roles

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

def _check_scopes(course):
	## CS: In alpha we have seen scopes missing its intids
	## Let's try to give it an intid
	intids = component.queryUtility(zope.intid.IIntIds)
	if intids is None:
		return
	for scope in course.SharingScopes.values():
		uid = intids.queryId(scope)
		obj = intids.queryObject(uid) if uid is not None else None
		if uid is None or obj != scope:
			if getattr( scope, '_p_jar', None ) is None:
				IConnection( course ).add( scope )

			if uid is not None and obj is None:
				logger.warn("Reregistering scope %s in course %r with intid facility",
							scope, course)
				intids.forceRegister(uid, scope)
			else:
				logger.warn("A new intid will be given to scope %s in course %r",
							scope, course)
				if hasattr(scope, intids.attribute):
					delattr(scope, intids.attribute)
				intids.register(scope)

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

	_check_scopes(course)

	role_manager = IPrincipalRoleManager(course)
	role_last_mod = getattr(role_manager, 'lastModified', 0)

	if key.lastModified <= role_last_mod:
		# JAM: XXX: We had some environments that got set up
		# before instructors were properly added to content roles;
		# rather than force environments to remove the role files and
		# sync, then put them back and sync again, I'm temporarily
		# setting roles each time we get here. It's an idempotent process,
		# though, so we won't be churning the database.
		for instructor in course.instructors:
			user = IUser(instructor)
			add_principal_to_course_content_roles(user, course)
		return role_manager

	reset_roles_missing_key(role_manager)

	__traceback_info__ = key, course
	json = key.readContentsAsYaml()
	_fill_roles_from_json(course, role_manager, json)
	role_manager.lastModified = key.lastModified

	# We must update the instructor list too, it's still used internally
	# in a few places...plus it's how we know who to remove from the scopes

	# Any instructors that were present but aren't present
	# anymore need to lose access to the sharing scopes
	orig_instructors = course.instructors

	course.instructors = ()

	# For any of these that exist as users, we need to make sure they
	# are in the appropriate sharing scopes too...
	# NOTE: We only take care of addition, we do not handle removal,
	# (that could be done with some extra work)

	for role_id, pid, setting in role_manager.getPrincipalsAndRoles():
		if setting is not Allow or role_id not in (RID_INSTRUCTOR, RID_TA):
			continue

		try:
			user = User.get_user(pid)
			course.instructors += (IPrincipal(user),)
		except (LookupError,TypeError):
			# lookuperror if we're not in a ds context,
			# TypeError if no named user was found and none was returned
			# and the adaptation failed
			pass
		else:
			# XXX: The addition and removal here are eerily similar
			# to what enrollment does and they've gotten out of sync
			# in the past.
			add_principal_to_course_content_roles(user, course)
			for scope in course.SharingScopes.values():
				# They're a member...
				user.record_dynamic_membership(scope)
				# ...and they follow it to get notifications of things
				# shared to it
				user.follow(scope)

			# If they're an instructor of a section, give them
			# access to the public community of the main course.
			if ICourseSubInstance.providedBy( course ):
				parent_course = course.__parent__.__parent__
				public_scope = parent_course.SharingScopes[ES_PUBLIC]
				user.record_dynamic_membership(public_scope)
				user.follow(public_scope)


	for orig_instructor in orig_instructors:
		if orig_instructor not in course.instructors:
			user = IUser(orig_instructor)
			# by definition here we have an IPrincipal that *came* from an IUser
			# and has a hard reference to it, and so can become an IUser again
			remove_principal_from_course_content_roles(user, course)
			for scope in course.SharingScopes.values():
				user.record_no_longer_dynamic_member(scope)
				user.stop_following(scope)

			# And remove access to the parent public scope.
			if ICourseSubInstance.providedBy( course ):
				parent_course = course.__parent__.__parent__
				public_scope = parent_course.SharingScopes[ES_PUBLIC]
				user.record_no_longer_dynamic_member(public_scope)
				user.stop_following(public_scope)

	return role_manager

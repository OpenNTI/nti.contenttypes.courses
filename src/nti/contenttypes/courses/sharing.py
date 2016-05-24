#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sharing support for courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# Despite the comments in interfaces.py, right now
# we still stick to a fairly basic Community-derived
# object for sharing purposes. This is largely for compatibility
# and will change.

from itertools import chain

from zope import component
from zope import interface

from zope.cachedescriptors.property import cachedIn

from zope.intid.interfaces import IIntIdAddedEvent
from zope.intid.interfaces import IIntIdRemovedEvent

from zope.lifecycleevent import IObjectMovedEvent
from zope.lifecycleevent import IObjectModifiedEvent

from zope.security.interfaces import IPrincipal

from ZODB.POSException import POSError

from nti.containers.containers import CheckingLastModifiedBTreeContainer

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseBundleUpdatedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScopes
from nti.contenttypes.courses.interfaces import ICourseInstanceImportedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import get_enrollments
from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_course_instructors

from nti.dataserver.authorization import _CommunityGroup
from nti.dataserver.authorization import CONTENT_ROLE_PREFIX
from nti.dataserver.authorization import role_for_providers_content

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IMutableGroupMember
from nti.dataserver.interfaces import IUseNTIIDAsExternalUsername

from nti.dataserver.users import User
from nti.dataserver.users import Community

from nti.externalization.oids import to_external_ntiid_oid

from nti.intid.wref import ArbitraryOrderableWeakRef

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import get_parts
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

@interface.implementer(ICourseInstanceSharingScope)
class CourseInstanceSharingScope(Community):
	"""
	A non-global sharing scope for a course instance.
	"""

	# does the UI need this? (Yes, at least the ipad does)
	__external_class_name__ = 'Community'
	mime_type = mimeType = 'application/vnd.nextthought.community'
	__external_can_create__ = False

	# Override things related to ntiids.
	# These don't have global names, so they must be referenced
	# by OID
	NTIID_TYPE = TYPE_OID
	NTIID = cachedIn('_v_ntiid')(to_external_ntiid_oid)

	# Likewise, externalization sometimes wants to spit out unicode(creator),
	# so we need to override that
	def __unicode__(self):
		ntiid = self.NTIID
		if ntiid is not None:
			return ntiid

		del self._v_ntiid
		# Sigh, probably in testing, we don't have an OID
		# or intid yet.
		return unicode(str(self))

	# We want, essentially, identity equality:
	# nothing is equal to this because nothing can be contained
	# in the same container as this

	def __eq__(self, other):
		if self is other: return True
		try:
			return self.NTIID == other.NTIID
		except AttributeError:
			return NotImplemented

	def __lt__(self, other):
		try:
			return self.NTIID < other.NTIID
		except AttributeError:
			return NotImplemented

# The scopes are a type of entity, but they aren't globally
# named or resolvable by username, so we need to use a better
# weak ref. Plus, there are parts of the code that expect
# IWeakRef to entity to have a username...
class _CourseInstanceSharingScopeWeakRef(ArbitraryOrderableWeakRef):

	@property
	def username(self):
		o = self()
		if o is not None:
			return o.NTIID

# Similarly for acting as principals
@interface.implementer(IUseNTIIDAsExternalUsername)
class _CourseInstanceSharingScopePrincipal(_CommunityGroup):

	def __init__(self, context):
		_CommunityGroup.__init__(self, context)
		# Overwrite id, which defaults to username, with ntiid
		self.id = context.NTIID
		self.NTIID = self.id  # also externalize this way

@interface.implementer(ICourseInstanceSharingScopes)
class CourseInstanceSharingScopes(CheckingLastModifiedBTreeContainer):
	"""
	Container for a course's sharing scopes.
	"""

	__external_can_create__ = False

	mime_type = mimeType = 'application/vnd.nextthought.courseinstancesharingscopes'

	def _vocabulary(self):
		# Could/should also use the vocabulary registry
		# and dispatch to adapters based on context
		return ENROLLMENT_SCOPE_VOCABULARY

	def __setitem__(self, key, value):
		if key not in self._vocabulary():
			raise KeyError("Unsupported scope kind", key)
		super(CourseInstanceSharingScopes, self).__setitem__(key, value)

	def initScopes(self):
		"""
		Make sure we have all the scopes specified by the vocabulary.
		"""
		for key in self._vocabulary():
			key = key.token
			if key not in self:
				self[key] = self._create_scope(key)

	def getAllScopesImpliedbyScope(self, scope_name):
		self.initScopes()
		# work with the global superset of terms, but only
		# return things in our local vocabulary
		term = ENROLLMENT_SCOPE_VOCABULARY.getTerm(scope_name)
		names = (scope_name,) + term.implies

		for name in names:
			try:
				scope = self[name]
				yield scope
			except KeyError:
				pass

	def _create_scope(self, name):
		return CourseInstanceSharingScope(name)

class CourseSubInstanceSharingScopes(CourseInstanceSharingScopes):
	"""
	The scopes created for a section/sub-instance, which
	handles the implication of joining the parent course scopes.
	"""

	__external_class_name__ = 'CourseInstanceSharingScopes'
	__external_can_create__ = False

	def getAllScopesImpliedbyScope(self, scope_name):
		# All of my scopes...
		for i in CourseInstanceSharingScopes.getAllScopesImpliedbyScope(self, scope_name):
			yield i

		# Plus all of the scopes of my parent course instance
		try:
			# me/subinstance/subinstances/course
			parent_course = self.__parent__.__parent__.__parent__
		except AttributeError:
			pass
		else:
			if parent_course is not None:
				scopes = parent_course.SharingScopes.getAllScopesImpliedbyScope(scope_name)
				for i in scopes:
					yield i

def _adjust_scope_membership(record, course,
							 join, follow,
							 ignored_exceptions=(),
							 currently_in=(),
							 relevant_scopes=None,
							 related_enrolled_courses=()):
	course = course or record.CourseInstance
	principal = record.Principal
	if principal is not None:
		join = getattr(principal, join)
		follow = getattr(principal, follow)
	else:
		join = follow = None

	scopes = course.SharingScopes

	if relevant_scopes is None:
		relevant_scopes = scopes.getAllScopesImpliedbyScope(record.Scope)

	scopes_to_ignore = []
	for related_course in related_enrolled_courses:
		sharing_scopes = related_course.SharingScopes
		scopes_to_ignore.extend(sharing_scopes.getAllScopesImpliedbyScope(record.Scope))

	for scope in relevant_scopes:
		if scope in currently_in:
			continue

		if scope in scopes_to_ignore:
			continue

		try:
			if join is not None:
				join(scope)
		except ignored_exceptions:
			pass

		try:
			if follow is not None:
				follow(scope)
		except ignored_exceptions:
			pass

def get_principal(principal):
	try:
		if principal is None or IUser(principal, None) is None:
			principal = None
	except (TypeError, POSError):
		principal = None
	return principal

def _content_roles_for_course_instance(course, packages=None):
	"""
	Returns the content roles for all the content packages
	in the course, if there are any.

	:return: A set.
	"""
	if packages is None:
		packages = get_course_packages(course)
	roles = []
	for pack in packages:
		ntiid = pack.ntiid
		ntiid = get_parts(ntiid)
		provider = ntiid.provider
		specific = ntiid.specific
		roles.append(role_for_providers_content(provider, specific))
	return set(roles)

def _principal_is_enrolled_in_related_course(principal, course):
	"""
	If the principal is enrolled in a parent or sibling course,
	return those courses.
	"""
	result = []
	potential_other_courses = []
	potential_other_courses.extend(course.SubInstances.values())
	if ICourseSubInstance.providedBy(course):
		main_course = course.__parent__.__parent__
		potential_other_courses.append(main_course)
		potential_other_courses.extend((x for x in main_course.SubInstances.values()
										if x is not course))

	principal = get_principal(principal)
	if principal is not None:
		for other in potential_other_courses:
			enrollments = ICourseEnrollments(other)
			if enrollments.get_enrollment_for_principal(principal) is not None:
				result.append(other)
	return tuple(result)

def add_principal_to_course_content_roles(principal, course, packages=None):
	if get_principal(principal) is None:
		return

	membership = component.getAdapter(principal, IMutableGroupMember,
									  CONTENT_ROLE_PREFIX)
	orig_groups = set(membership.groups)
	new_groups = _content_roles_for_course_instance(course, packages)

	final_groups = orig_groups | new_groups
	if final_groups != orig_groups:
		# be idempotent
		membership.setGroups(final_groups)

def _get_principal_enrollment_packages(principal, courses_to_exclude=()):
	"""
	Gather the set of course packages for the principal's enrollments,
	excluding any courses given.
	"""
	result = set()
	enrollments = get_enrollments(principal.username)
	for record in enrollments:
		course = ICourseInstance(record, None)  # dup enrollment
		if 		course is not None \
			and course not in courses_to_exclude:
			packages = get_course_packages(course)
			result.update(packages)
	return result

def remove_principal_from_course_content_roles(principal, course, packages=None):
	"""
	Remove the principal from the given course roles (and optional packages).
	We must verify the principal does not have access to this content
	outside of the given course.
	"""
	if get_principal(principal) is None:
		return

	if not packages:
		packages = get_course_packages(course)

	# Get the minimal set of packages to remove roles for.
	enrollment_packages = _get_principal_enrollment_packages(principal,
															 courses_to_exclude=(course,))
	to_remove = set(packages) - enrollment_packages

	roles_to_remove = _content_roles_for_course_instance(course, to_remove)
	membership = component.getAdapter(principal, IMutableGroupMember,
									  CONTENT_ROLE_PREFIX)
	groups = set(membership.groups)
	new_groups = groups - roles_to_remove
	if new_groups != groups:
		membership.setGroups(new_groups)

@component.adapter(ICourseInstanceEnrollmentRecord, IIntIdAddedEvent)
def on_enroll_record_scope_membership(record, event, course=None):
	"""
	When you enroll in a course, record your membership in the
	proper scopes, including content access.
	"""
	_adjust_scope_membership(record, course,
							 'record_dynamic_membership',
							 'follow')
	# Add the content roles
	add_principal_to_course_content_roles(record.Principal,
										  course or record.CourseInstance)

# We may have intid-weak references to these things,
# so we need to catch them on the IntIdRemoved event
# for dependable ordering
@component.adapter(ICourseInstanceEnrollmentRecord, IIntIdRemovedEvent)
def on_drop_exit_scope_membership(record, event, course=None):
	"""
	When you drop a course, leave the scopes you were in, including
	content access.
	"""

	principal = get_principal(record.Principal)
	course = course or record.CourseInstance

	related_enrolled_courses = \
			_principal_is_enrolled_in_related_course(principal, course)

	# If the course was in the process of being deleted,
	# the sharing scopes may already have been deleted, which
	# shouldn't be a problem: the removal listeners for those
	# events should have cleaned up
	_adjust_scope_membership(record, course,
							 'record_no_longer_dynamic_member',
							 'stop_following',
							 # Depending on the order, we may have already
							 # cleaned this up (e.g, deleting a principal
							 # fires events twice due to various cleanups)
							 # So the entity may no longer have an intid -> KeyError
							 ignored_exceptions=(KeyError,),
							 related_enrolled_courses=related_enrolled_courses)

	remove_principal_from_course_content_roles(principal, course)

@component.adapter(ICourseInstanceEnrollmentRecord, IObjectModifiedEvent)
def on_modified_update_scope_membership(record, event):
	"""
	When your enrollment record is modified, update the scopes
	you should be in.
	"""
	# It would be nice if we could guarantee that
	# the event had its descriptions attribute filled out
	# so we could be sure it was the Scope that got modified,
	# but we can't

	# Try hard to avoid firing events for scopes we don't actually
	# need to exit or add
	principal = get_principal(record.Principal)
	if principal is None:
		return

	sharing_scopes = record.CourseInstance.SharingScopes

	scopes_i_should_be_in = sharing_scopes.getAllScopesImpliedbyScope(record.Scope)
	scopes_i_should_be_in = list(scopes_i_should_be_in)

	drop_from = []
	currently_in = []
	for scope in sharing_scopes.values():
		if principal in scope:
			if scope in scopes_i_should_be_in:
				# A keeper!
				currently_in.append(scope)
			else:
				drop_from.append(scope)

	# First, the drops
	_adjust_scope_membership(record, None,
							 'record_no_longer_dynamic_member',
							 'stop_following',
							 relevant_scopes=drop_from)

	# Now any adds
	_adjust_scope_membership(record, None,
							 'record_dynamic_membership',
							 'follow',
							 currently_in=currently_in,
							 relevant_scopes=scopes_i_should_be_in)

@component.adapter(ICourseInstanceEnrollmentRecord, IObjectMovedEvent)
def on_moved_between_courses_update_scope_membership(record, event):
	"""
	We rely on the CourseInstance being in the lineage of the record
	so that we can find the instance that was \"dropped\" by traversing
	through the old parents.
	"""

	# This gets called when we are added or removed, because those
	# are both kinds of Moved events. But we only want this for a true
	# move
	if event.oldParent is None or event.newParent is None:
		return

	old_course = find_interface(event.oldParent, ICourseInstance)
	new_course = find_interface(event.newParent, ICourseInstance)

	assert new_course is record.CourseInstance

	on_drop_exit_scope_membership(record, event, old_course)
	on_enroll_record_scope_membership(record, event, new_course)

@component.adapter(ICourseInstance, ICourseBundleUpdatedEvent)
def update_package_permissions(course, event):
	"""
	Update the package permissions for the enrollees, instructors
	and editors of this course if packages have been added/removed.
	"""
	enrollments = ICourseEnrollments(course)
	if not event.added_packages and not event.removed_packages:
		# Nothing to do
		return

	entry = ICourseCatalogEntry(course)
	logger.info('Updating package permissions for course (%s)', entry.ntiid)
	for principal in chain(enrollments.iter_principals(),
							get_course_instructors(course),
							get_course_editors(course)):
		if IPrincipal.providedBy(principal):
			principal = principal.id
		if not IUser.providedBy(principal):
			principal = User.get_user(principal)
		if event.added_packages:
			add_principal_to_course_content_roles(principal,
										  		  course,
										  		  event.added_packages)

		if event.removed_packages:
			remove_principal_from_course_content_roles(principal,
													   course,
													   event.removed_packages)

@component.adapter(ICourseInstance, ICourseInstanceImportedEvent)
def on_course_instance_imported(course, event):
	enrollments = ICourseEnrollments(course)
	for principal in chain(enrollments.iter_principals(),
							get_course_instructors(course),
							get_course_editors(course)):
		if IPrincipal.providedBy(principal):
			principal = principal.id
		if not IUser.providedBy(principal):
			principal = User.get_user(principal)
		add_principal_to_course_content_roles(principal, course)

def get_default_sharing_scope(context):
	"""
	Returns the configured default scope for the context.
	"""
	course = ICourseInstance(context)
	vendor_info = ICourseInstanceVendorInfo(course, {})
	result = None
	try:
		result = vendor_info['NTI']['DefaultSharingScope']
	except (TypeError, KeyError):
		pass
	else:
		# Could have ntiid or special string
		if is_valid_ntiid_string(result):
			result = find_object_with_ntiid(result)
		else:
			# Ex: Parent/Public or Public
			parts = result.split('/')
			scope = parts[0]

			if len(parts) > 1:
				# We reference a scope in our parent.
				scope = parts[1]
				assert	ICourseSubInstance.providedBy(context), \
						"DefaultSharingScope referencing parent of top-level course."
				# TODO Is this correct, or only correct for Public?
				course = context.__parent__.__parent__
			result = course.SharingScopes[ scope ]
	return result

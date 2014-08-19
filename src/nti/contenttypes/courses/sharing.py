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

from zope import interface
from zope import component
from zope.cachedescriptors.property import cachedIn

from .interfaces import ICourseSubInstance
from .interfaces import ICourseEnrollments
from .interfaces import ICourseInstanceSharingScope
from .interfaces import ICourseInstanceSharingScopes
from .interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.dataserver.users import Community
from nti.ntiids.ntiids import TYPE_OID
from nti.externalization.oids import to_external_ntiid_oid

from nti.dataserver.containers import CheckingLastModifiedBTreeContainer

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
from nti.intid.wref import ArbitraryOrderableWeakRef
class _CourseInstanceSharingScopeWeakRef(ArbitraryOrderableWeakRef):

	@property
	def username(self):
		o = self()
		if o is not None:
			return o.NTIID

# Similarly for acting as principals
from nti.dataserver.authorization import _CommunityGroup
from nti.dataserver.interfaces import IUseNTIIDAsExternalUsername
@interface.implementer(IUseNTIIDAsExternalUsername)
class _CourseInstanceSharingScopePrincipal(_CommunityGroup):

	def __init__(self, context):
		_CommunityGroup.__init__(self, context)
		# Overwrite id, which defaults to username, with ntiid
		self.id = context.NTIID
		self.NTIID = self.id # also externalize this way

@interface.implementer(ICourseInstanceSharingScopes)
class CourseInstanceSharingScopes(CheckingLastModifiedBTreeContainer):
	"""
	Container for a course's sharing scopes.
	"""

	__external_can_create__ = False

	def _vocabulary(self):
		# Could/should also use the vocabulary registry
		# and dispatch to adapters based on context
		return ENROLLMENT_SCOPE_VOCABULARY

	def __setitem__(self, key, value):
		if key not in self._vocabulary():
			raise KeyError("Unsupported scope kind", key)
		super(CourseInstanceSharingScopes,self).__setitem__(key, value)

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
				for i in parent_course.SharingScopes.getAllScopesImpliedbyScope(scope_name):
					yield i

###
# Event handling to get sharing correct.
###

from .interfaces import ICourseInstanceEnrollmentRecord
from zope.lifecycleevent import IObjectModifiedEvent
from zope.lifecycleevent import IObjectMovedEvent
# We may have intid-weak references to these things,
# so we need to catch them on the IntIdRemoved event
# for dependable ordering
from zope.intid.interfaces import IIntIdAddedEvent
from zope.intid.interfaces import IIntIdRemovedEvent


def _adjust_scope_membership(record, course,
							 join, follow,
							 ignored_exceptions=(),
							 currently_in=(),
							 relevant_scopes=None):
	course = course or record.CourseInstance
	principal = record.Principal
	join = getattr(principal, join)
	follow = getattr(principal, follow)
	scopes = course.SharingScopes

	if relevant_scopes is None:
		relevant_scopes = scopes.getAllScopesImpliedbyScope(record.Scope)
	for scope in relevant_scopes:
		if scope in currently_in:
			continue

		try:
			join(scope)
		except ignored_exceptions:
			pass

		try:
			follow(scope)
		except ignored_exceptions:
			pass

from nti.dataserver.interfaces import IMutableGroupMember
from nti.dataserver.authorization import CONTENT_ROLE_PREFIX
from nti.dataserver.authorization import role_for_providers_content
from nti.ntiids import ntiids

def _content_roles_for_course_instance(course):
	"""
	Returns the content roles for all the content packages
	in the course, if there are any.

	:return: A set.
	"""
	bundle = getattr(course, 'ContentPackageBundle', None)
	packs = getattr(bundle, 'ContentPackages', ())
	roles = []
	for pack in packs:
		ntiid = pack.ntiid
		ntiid = ntiids.get_parts(ntiid)
		provider = ntiid.provider
		specific = ntiid.specific
		roles.append(role_for_providers_content(provider, specific))
	return set(roles)

def add_principal_to_course_content_roles(principal, course):
	membership = component.getAdapter(principal, IMutableGroupMember, CONTENT_ROLE_PREFIX)
	orig_groups = set(membership.groups)
	new_groups = _content_roles_for_course_instance(course)

	final_groups = orig_groups | new_groups
	if final_groups != orig_groups:
		# be idempotent
		membership.setGroups(final_groups)

def remove_principal_from_course_content_roles(principal, course, roles_to_remove=None):
	roles_to_remove = roles_to_remove or _content_roles_for_course_instance(course)
	membership = component.getAdapter(principal, IMutableGroupMember, CONTENT_ROLE_PREFIX)
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
							 'follow' )
	# Add the content roles
	add_principal_to_course_content_roles(record.Principal, course or record.CourseInstance)

@component.adapter(ICourseInstanceEnrollmentRecord, IIntIdRemovedEvent)
def on_drop_exit_scope_membership(record, event, course=None):
	"""
	When you drop a course, leave the scopes you were in, including
	content access.
	"""
	# If the course was in the process of being deleted,
	# the sharing scopes may already have been deleted, which
	# shouldn't be a problem: the removal listeners for those
	# events should have cleaned up
	_adjust_scope_membership( record, course,
							  'record_no_longer_dynamic_member',
							  'stop_following',
							  # Depending on the order, we may have already
							  # cleaned this up (e.g, deleting a principal
							  # fires events twice due to various cleanups)
							  # So the entity may no longer have an intid -> KeyError
							  ignored_exceptions=(KeyError,))

	principal = record.Principal
	course = course or record.CourseInstance
	if not ICourseSubInstance.providedBy(course):
		## CS: If the user is droping from a parent course
		## check to see if user is enrolled in any of its sub instances 
		## then only remove access to content that is not shared amongst
		## them.
		course_roles = _content_roles_for_course_instance(course)
		for subInstance in course.SubInstances.values():
			enrollments = ICourseEnrollments(subInstance)
			record = enrollments.get_enrollment_for_principal(principal)
			if record is not None:
				subInstance_roles = _content_roles_for_course_instance(subInstance)
				course_roles = course_roles.difference(subInstance_roles)
		
		if course_roles:
			remove_principal_from_course_content_roles(principal, course, course_roles)
	else:
		# Remove the content roles
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
	principal = record.Principal
	sharing_scopes = record.CourseInstance.SharingScopes
	scopes_i_should_be_in = list(sharing_scopes.getAllScopesImpliedbyScope(record.Scope))
	currently_in = []
	drop_from = []
	for scope in sharing_scopes.values():
		if principal in scope:
			if scope in scopes_i_should_be_in:
				# A keeper!
				currently_in.append(scope)
			else:
				drop_from.append(scope)

	# First, the drops
	_adjust_scope_membership( record, None,
							  'record_no_longer_dynamic_member',
							  'stop_following',
							  relevant_scopes=drop_from)

	# Now any adds
	_adjust_scope_membership( record, None,
							  'record_dynamic_membership',
							  'follow',
							  currently_in=currently_in,
							  relevant_scopes=scopes_i_should_be_in)

from nti.dataserver.traversal import find_interface
from .interfaces import ICourseInstance

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

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

	# does the UI need this?
	#__external_class_name__ = 'Community'
	#mime_type = mimeType = 'application/vnd.nextthought.community'
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

	def __iter__(self):
		# For testing convenience
		return self.iter_members()


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
class _CourseInstanceSharingScopePrincipal(_CommunityGroup):

	def __init__(self, context):
		_CommunityGroup.__init__(self, context)
		# Overwrite id, which defaults to username, with ntiid
		self.id = context.NTIID

@interface.implementer(ICourseInstanceSharingScopes)
class CourseInstanceSharingScopes(CheckingLastModifiedBTreeContainer):
	"""
	Container for a course's sharing scopes.
	"""

	def __setitem__(self, key, value):
		if key not in ENROLLMENT_SCOPE_VOCABULARY:
			raise KeyError("Unsupported scope kind", key)
		super(CourseInstanceSharingScopes,self).__setitem__(key, value)


	def getAllScopesImpliedbyScope(self, scope_name):
		term = ENROLLMENT_SCOPE_VOCABULARY.getTerm(scope_name)
		names = (scope_name,) + term.implies

		for name in names:
			try:
				scope = self[name]
			except KeyError:
				scope = self[name] = self._create_scope(name)
			yield scope

	def _create_scope(self, name):
		return CourseInstanceSharingScope(name)

###
# Event handling to get sharing correct.
###

from .interfaces import ICourseInstanceEnrollmentRecord
from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectRemovedEvent
from zope.lifecycleevent import IObjectModifiedEvent

def _adjust_scope_membership(record, join, follow):
	course = record.CourseInstance
	principal = record.Principal
	join = getattr(principal, join)
	follow = getattr(principal, follow)
	scopes = course.SharingScopes

	relevant_scopes = scopes.getAllScopesImpliedbyScope(record.Scope)
	for scope in relevant_scopes:
		join(scope)
		follow(scope)


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectAddedEvent)
def on_enroll_record_scope_membership(record, event):
	"""
	When you enroll in a course, record your membership in the
	proper scopes.
	"""
	_adjust_scope_membership(record,
							 'record_dynamic_membership',
							 'follow' )


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectRemovedEvent)
def on_drop_exit_scope_membership(record, event):
	"""
	When you drop a course, leave the scopes you were in.
	"""

	_adjust_scope_membership( record,
							  'record_no_longer_dynamic_member',
							  'stop_following')

@component.adapter(ICourseInstanceEnrollmentRecord, IObjectModifiedEvent)
def on_modified_update_scope_membership(record, event):
	"""
	When your enrollment record is modified, update the scopes
	you should be in.
	"""

	raise NotImplementedError()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Course-related interfaces.

Most course-related objects are also folders containing
subobjects, and they are also :class:`.IPossibleSite` objects
for local policy containment (including things like default
preferences). The expected contents of each type of object
are explained on the object itself.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# disable: too many ancestors, missing 'self''
# pylint: disable=I0011,R0901,E0213

from . import MessageFactory as _

from zope import interface
from zope.interface.common.mapping import IEnumerableMapping

from zope.security.interfaces import IPrincipal

from zope.site.interfaces import IFolder

from zope.container.interfaces import IContainer
from zope.container.interfaces import IContained
from zope.container.interfaces import IContentContainer
from zope.container.interfaces import IOrderedContainer
from zope.container.interfaces import IContainerNamesContainer

from zope.container.constraints import contains
from zope.container.constraints import containers

from nti.contentlibrary.interfaces import IDisplayableContent
from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IEnumerableDelimitedHierarchyBucket

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import ILastModified
from nti.dataserver.interfaces import ITitledDescribedContent
from nti.dataserver.interfaces import IShouldHaveTraversablePath
from nti.dataserver.interfaces import IUseNTIIDAsExternalUsername

from nti.dataserver.contenttypes.forums.interfaces import IBoard

from nti.ntiids.schema import ValidNTIID

from nti.schema.field import Choice
from nti.schema.field import Object
from nti.schema.field import Number
from nti.schema.field import Timedelta
from nti.schema.field import ValidText
from nti.schema.field import ListOrTuple
from nti.schema.field import ValidDatetime
from nti.schema.field import ValidTextLine
from nti.schema.field import UniqueIterable

# Permissions defined for courses here should also be
# registered in ZCML:
# from zope.security.permission import Permission
# ACT_XXX = Permission('nti.actions.XXX')

# Roles defined and used by this package

#: The ID of a role for instructors
RID_INSTRUCTOR = "nti.roles.course_instructor"

#: The ID of a role for teaching assistants
RID_TA = "nti.roles.course_ta"

###
# Notes:
#
# How to determine available courses?
#  -- Could either enumerate, or we maintain
#     a zope.catalog.Catalog (probably a catalog long term)
#
# How to tell what a user is enrolled in?
#  -- We could also use a zope.catalog.Catalog here,
#     but enrollment status effects permissioning,
#     not just of UGD (which previously was handled
#     implicitly through sharing things with a specific
#     DFL) but also of content. That means that
#     ACLs and "effective principals" get involved.
#     This could still be done with a DFL 'owned' by the
#     CourseInstance object, but a hierarchy can be extremely
#     useful (e.g., all students, ou students, ou grad students).
#     A hierarchy is offered by IPrincipal/IGroup and the
#     use of zope.pluggableauth.plugins.groupfolder,
#     so that's probably what we'll go with.
#
#     The remaining question is where the groupfolders live. pluggableauth
#     uses IAuthentication utilities, which are usually persistent
#     and which become active through traversal. If the groupfolder
#     is local to each ICourseInstance's SiteManager, this is handy
#     for permissioning and local editing, but not for global
#     queries. I really like the idea of local groupfolders,
#     so we may punt on that for now and do some sort of a
#     (cached) global enumeration when necessary until we
#     either do a catalog or manually keep a second datastructure.

class ICourseAdministrativeLevel(IFolder):
	"""
	A container representing a level at which
	courses are administered. Specific instances
	or specific sub-interfaces may represent
	things like an organization or a department.

	Typically this will contain either other policy
	containers or instances of courses.
	"""

	contains(str('.ICourseInstance'),
			 str('.ICourseAdministrativeLevel'))
	__setitem__.__doc__ = None

###
# Outlines
###

class _ICourseOutlineNodeContainer(interface.Interface):
	"""
	Internal container for outline nodes.
	"""

class ICourseOutlineNode(ITitledDescribedContent,
						 IOrderedContainer,
						 IContainerNamesContainer,
						 _ICourseOutlineNodeContainer):
	"""
	A part of the course outline. Children are the sub-nodes of this
	entity, and are (typically) named numerically.

	.. note:: This is only partially modeled.
	"""

	containers(str('._ICourseOutlineNodeContainer'))
	contains(str('.ICourseOutlineNode'))
	__parent__.required = False
	__setitem__.__doc__ = None

	src = ValidTextLine(title="json file to populate the node overview",
						required=False)

	def append(node):
		"A synonym for __setitem__ that automatically handles naming."

class ICourseOutlineCalendarNode(ICourseOutlineNode):
	"""
	A part of the course outline that may have specific calendar dates
	associated with it. Because they still have titles and
	descriptions but carry no other information, they may be used as
	markers of some kind, such as a 'placeholder' for content that
	isn't ready yet, or a grouping structure.
	"""

	ContentNTIID = interface.Attribute('ContentNTIID',
									   "A non-schema place (so not externalized) that can store"
									   "a placeholder content-ntiid, if it is known.")
	ContentNTIID.setTaggedValue('_ext_excluded_out', True)

	AvailableBeginning = ValidDatetime(
		title="This node is available, or expected to be entered or active at this time",
		description="""When present, this specifies the time instant at which
		this node and its children are to be available or active. If this is absent,
		it is always available or active. While this is represented here as an actual
		concrete timestamp, it is expected that in many cases the source representation
		will be relative to something else (a ``timedelta``) and conversion to absolute
		timestamp will be done as needed.""",
		required=False)

	AvailableEnding = ValidDatetime(
		title="This node is completed and no longer available at this time",
		description="""When present, this specifies the last instance at which
		this node is expected to be available and active.
		As with ``available_for_submission_beginning``,
		this will typically be relative and converted.""",
		required=False )

class ICourseOutlineContentNode(ICourseOutlineCalendarNode):
	"""
	A part of a course outline that refers to
	a content unit.
	"""

	ContentNTIID =  ValidNTIID(title="The NTIID of the content this node uses")

class ICourseOutline(ICourseOutlineNode,
					 ILastModified):
	"""
	The schedule or syllabus of the course, defined
	in a recursive tree-like structure.

	.. note:: The nodes are only partially modeled.
	"""

	# NOTE: We are currently hanging these off of the
	# course instance. That may not be the best place for two reasons:
	# First, we may want to provide access to these before
	# enrollment (as part of the course catalog), and ACLs might
	# prevent simple access to children of a course to non-enrolled
	# principals. That's surmountable though.
	# Second, we may be dynamically generating or filtering the
	# syllabus/outline based on the active principal, and unless
	# extreme care is taken with the URL structure, we could
	# run into caching issues (see the MD5 hacks for forums).
	containers(str('.ICourseInstance'))
	__parent__.required = False


###
# Sharing
###

# Despite the notes at the top of this file about group-folders,
# we still stick to a fairly basic Community-derived
# object for sharing purposes. This is largely for compatibility
# and will change.

class ICourseInstanceSharingScope(ICommunity,
								  IUseNTIIDAsExternalUsername):
	"""
	A sharing scope within an instance.
	"""

	containers(str('.ICourseInstanceSharingScopes'))
	__parent__.required = False


class ICourseInstanceSharingScopes(IContainer):
	"""
	A container of sharing scopes for the course.

	See the documentation for :class:`ICourseInstanceEnrollmentRecord`
	for the expected keys in this scope.
	"""

	contains(ICourseInstanceSharingScope)
	containers(str('.ICourseInstance'))
	__parent__.required = False
	__setitem__.__doc__ = None

	def getAllScopesImpliedbyScope(scope_name):
		"""
		Return all the :class:`ICourseInstanceSharingScope` objects
		implied by the given scope name, including the scope itself,
		creating them if necessary.
		"""

###
# Discussions
###

from nti.dataserver.contenttypes.forums.interfaces import ICommunityBoard
from nti.dataserver.contenttypes.forums.interfaces import ICommunityForum
from nti.dataserver.contenttypes.forums.interfaces import IUseOIDForNTIID

class ICourseInstanceBoard(IUseOIDForNTIID,
						   ICommunityBoard):
	"""
	Specialization of boards for courses.

	Note that courses are not required to contain
	this type of board in their Discussions property
	(for BWC, mostly), but this is required to be
	contained by a course.
	"""
	containers(str('.ICourseInstance'))

class ICourseInstanceForum(ICommunityForum):
	"""
	A forum associated with a course board.
	"""
	# we don't put a containers restriction on this,
	# we expect some legacy implementations that aren't actually
	# contained in course boards

class ICourseInstanceScopedForum(ICourseInstanceForum):
	"""
	A forum associated with a course, intended to be viewable
	only by a certain enrollment scope within that course.
	"""

	SharingScopeName = interface.Attribute("an optional field that should match the name of a sharing scope;"
										   "If not found also check the tagged value on this attribute")

###
# Course instances
###

class ICourseSubInstances(IContainer):
	"""
	A container for the subinstances (sections) of a course.
	"""

	contains(str('.ICourseSubInstance'))
	containers(str('.ICourseInstance'))
	__parent__.required = False
	__setitem__.__doc__ = None

class ISynchronizable(interface.Interface):
	lastSynchronized = Number(title=u"The timestamp at which this object was last synchronized .",
						  	  default=0.0)
	lastSynchronized.setTaggedValue('_ext_excluded_out', True)

class ICourseInstance(IFolder,
					  IShouldHaveTraversablePath,
					  _ICourseOutlineNodeContainer,
					  ISynchronizable):
	"""
	A concrete instance of a course (typically
	in progress or opening). This can be annotated,
	which may be how things like a gradebook are attached
	to it.

	Contents are generally undefined. There may be specialized
	sub-contents for things like particular sections, which get most
	of their info from acquisition of this object. Or we may need to
	keep (HTML/PDF) content here. As contents are defined, list them
	here and in the ``contains`` constraint.

	Instances may be adaptable to :class:`.IDisplayableContent`.
	"""

	containers(ICourseAdministrativeLevel,
			   ICourseSubInstances)
	__parent__.required = False

	SharingScopes = Object(ICourseInstanceSharingScopes,
						   title="The sharing scopes for this instance",
						   description="Each course has one or more sharing scopes. "
						   "See :class:`ICourseInstanceEnrollmentRecord` for details.")
	# SharingScopes are externalized via a decorator to take into account
	# membership
	SharingScopes.setTaggedValue('_ext_excluded_out', True)

	Discussions = Object(IBoard,
						 title="The root discussion board for this course.",
						 description="Typically, courses will 'contain' their own discussions, "
						 "but this may be a reference to another object.")

	Outline = Object(ICourseOutline,
					 title="The course outline or syllabus, if there is one.",
					 required=False)

	SubInstances = Object(ICourseSubInstances,
						  title="The sub-instances of this course, if any")
	SubInstances.setTaggedValue('_ext_excluded_out', True)

	## Reflecting instructors, TAs, and other affiliated
	## people with a special role in the course:
	# This could be done in a couple ways. We could define a generic
	# "role" object, and have a list of roles and their occupants.
	# This is flexible, but not particularly high on ease-of-use.
	# Alternately, we could expose each relationship as a named
	# attribute: not flexible, but easy to use, so that's
	# what we're going with now
	# (Internally, the contents of these attributes could
	# come from a role in the groupfolder of the site manager,
	# or somewhere else.)

	# The enrolled list of students is not part of this interface,
	# it is a separate adapter because that information might not
	# generally be available.

	# These are lower-case attributes because someone might be able to
	# edit them through-the-web?

	## XXX: JAM: 20140716: The above description has now been surpassed,
	# and we are in fact using a structured role model. The use of
	# this attribute is deprecated. It in fact holds everyone, both
	# instructors and TAs and others.
	instructors = UniqueIterable(title="The principals that are the intsructors of the course.",
								 description="They get special access rights.",
								 value_type=Object(IPrincipal))
	instructors.setTaggedValue('_ext_excluded_out', True)

class ICourseSubInstance(ICourseInstance):
	"""
	A portion or section of a course instance that lives within a
	containing course instance. The containing course instance will
	provide any properties not specifically provided by this object
	(e.g., it will acquire them through its parents).

	When externalized, this object gains the following properties:

	* ``ParentSharingScopes`` is a sharing scopes object having
		all the scopes from the parent course the current user is a
		member of.
	* ``ParentDiscussions`` is a pointer to the discussion board
		of the parent course.
	"""
	interface.taggedValue('__external_class_name__', 'CourseInstance')


class IContentCourseInstance(ICourseInstance):
	"""
	A type of course instance closely associated with
	content.
	"""

	# JAM: Although it might seem convenient to make
	# a CourseInstance is-a ContentBundle,
	# that muddies inheritance substantially and requires
	# all kinds of weird configuration rules because we don't
	# want to inherit what the content bundle has, such as
	# discussions. In addition, we want to have the possibility
	# that the same content bundle is used both inside and outside
	# of a course context (though the initial implementation )

	ContentPackageBundle = Object(IContentPackageBundle,
								  title="The content package associated with this course.")


	root = Object(IEnumerableDelimitedHierarchyBucket,
				  title="The on-disk bucket containing descriptions for this object",
				  default=None,
				  required=False)
	root.setTaggedValue('_ext_excluded_out', True)

class IContentCourseSubInstance(ICourseSubInstance,IContentCourseInstance):
	pass

class IEnrollmentMappedCourseInstance(ICourseInstance):
	"""
	A type of course instance that has its enrollment scopes specially
	mapped.

	We expect to find vendor info like this::

	    NTI: {
	        EnrollmentMap: {
	            scope_name: section_name,
	        }
	    }
	"""
# Don't try to consider this when determining most-derived
# interfaces. (This one does need to be a kind-of ICourseInstance because
# we want to register enrollment managers for it.)
IEnrollmentMappedCourseInstance.setTaggedValue('_ext_is_marker_interface', True)

class ICourseInstanceVendorInfo(IEnumerableMapping,
								ILastModified,
								IContained):
	"""
	Arbitrary course vendor-specific information associated with a
	course instance. Courses should be adaptable to their vendor
	info.

	This is simply a dictionary and this module does not define
	the structure of it. However, it is recommended that the top-level
	keys be the vendor names and within them be the actual vendor specific
	information.
	"""

ICourseInstanceVenderInfo = ICourseInstanceVendorInfo # both spellings are acceptable

class INonPublicCourseInstance(interface.Interface):
	"""
	A marker interface applied to course instances to designate
	that they are not \"open\" to the public. Only
	people enrolled for credit can see the catalog entry and the
	course itself. This enrollment typically happens in a backend
	process.
	"""
# Don't try to consider this when determining most-derived
# interfaces.
INonPublicCourseInstance.setTaggedValue('_ext_is_marker_interface', True)

class IDenyOpenEnrollment(interface.Interface):
	"""
	A marker interface applied to course instances to designate
	that they don't allow open enrollment
	people enrolled for credit can see the catalog entry and the
	course itself. This enrollment typically happens in a backend
	process.
	"""
IDenyOpenEnrollment.setTaggedValue('_ext_is_marker_interface', True)

from zope.location import LocationIterator

def is_instructed_by_name(context, username):
	"""
	Checks if the context is within something instructed
	by the given principal id. The context will be searched
	for an ICourseInstance.

	If either the context or username is missing, returns
	a false value.

	This is semi-deprecated; switch to using explicit permissions
	granted to roles such as the :const:`RID_INSTRUCTOR` role
	and :func:`zope.security.management.checkPermission`.
	"""

	if username is None or context is None:
		return None

	course = None
	for x in LocationIterator(context):
		course = ICourseInstance(x, None)
		if course is not None:
			break

	if course is None:
		return False

	return any((username == instructor.id for instructor in course.instructors))

###
# Catalog
###

class ICourseCatalog(interface.Interface):
	"""
	Something that manages the set of courses available in the system
	and provides ways to query for courses and find out information
	about them.

	Implementations that live in sites are expected to be able
	to query up the tree for additional course catalog entries.
	"""

	def isEmpty():
		"""
		Return if this catalog is empty. Does not take the site hierarchy into
		account.
		"""

	def iterCatalogEntries():
		"""
		Iterate across the installed catalog entries.

		Entries from this site level shadow entries from
		higher site levels, and entries from this site
		level are returned first.
		"""

	def getCatalogEntry(name):
		"""
		Retrieve a catalog entry by name. Entries from this
		site level shadow entries from higher site levels.

		:raises KeyError: If no such named entry can
			be found.
		"""

from persistent.interfaces import IPersistent

class IPersistentCourseCatalog(ICourseCatalog,
							   IPersistent):
	"""
	A locally persistent course catalog; contrast with the global
	course catalog.
	"""

class IWritableCourseCatalog(ICourseCatalog,IContentContainer):
	"""
	A type of course catalog that is expected to behave like
	a container and be writable.
	"""

	contains(b'.ICourseCatalogEntry')
	__setitem__.__doc__ = None

	def addCatalogEntry(entry, event=True):
		"""
		Adds an entry to this catalog.

		:keyword bool event: If true (the default), we broadcast
			the object added event.
		"""

	def removeCatalogEntry(entry, event=True):
		"""
		Remove an entry from this catalog.

		:keyword bool event: If true (the default), we broadcast
			the object removed event.
		"""

class IGlobalCourseCatalog(IWritableCourseCatalog):
	"""
	A course catalog intended to be registered at the global
	level as the root (or within z3c.baseregistry components
	that are not persistent.)
	"""

class ICourseCatalogInstructorInfo(interface.Interface):
	"""
	Information about a course instructor.

	.. note:: Almost all of this could/should
		come from a user profile. That way the user
		can be in charge of it. Pictures would come from
		the user's avatar URL.
	"""

	Name = ValidTextLine(title="The instructor's name")
	Title = ValidTextLine(title="The instructor's title of address such as Dr.",
							required=False)
	JobTitle = ValidTextLine(title="The instructor's academic job title")
	Suffix = ValidTextLine(title="The instructor's suffix such as PhD or Jr",
							 required=False)

class ICourseCatalogEntry(IDisplayableContent,
						  ILastModified,
						  IShouldHaveTraversablePath,
						  IContained,
						  ISynchronizable):
	"""
	An entry in the course catalog containing metadata
	and presentation data about the course.

	Much of this is poorly modeled and a conglomeration of things
	found in several previous places.

	In general, these objects should be adaptable to their
	corresponding :class:`.ICourseInstance`, and the
	course instance should be adaptable back to its corresponding
	entry.
	"""

	containers(ICourseCatalog)
	__parent__.required = False

	# Used to have Title/Description, now the lower case versions.
	# The T/D should be aliased in implementations.

	ProviderUniqueID = ValidTextLine(title="The unique id assigned by the provider")
	ProviderDepartmentTitle = ValidTextLine(title="The string assigned to the provider's department offering the course")

	Instructors = ListOrTuple(title="The instuctors. Order might matter",
									 value_type=Object(ICourseCatalogInstructorInfo) )

	InstructorsSignature = ValidText(title="The sign-off or closing signature of the instructors",
									 description="As used in an email. If this is not specifically provided, "
									 "one can be derived from the names and titles of the instructors.")
	InstructorsSignature.setTaggedValue('_ext_excluded_out', True)

	### Things related to the availability of the course
	StartDate = ValidDatetime(title="The date on which the course begins",
						 description="Currently optional; a missing value means the course already started")
	Duration = Timedelta(title="The length of the course",
						 description="Currently optional, may be None")
	EndDate = ValidDatetime(title="The date on which the course ends",
					   description="Currently optional; a missing value means the course has no defined end date.")

	def isCourseCurrentlyActive():
		"""
		Return a boolean value answering whether the course
		should be considered active, taking into account any information
		about starting and ending dates and durations, preview
		flags, etc.
		"""

###
# Enrollments
###

# Now we list the scopes and create a vocabulary
# for them. In the future, we can use a vocabularyregistry
# to have these be site-specific.


#: The "root" enrollment or sharing scope; everyone enrolled or administrating
#: is a member of this scope.
#: sharing scopes are conceptually arranged in a strict hierarchy, and
#: every enrollment record is within one specific scope. Because
#: scope objects do not actually nest (are non-transitive), it is implied that
#: a member of a nested scope will actually also be members of
#: the parent scopes.
ES_PUBLIC = "Public"

#: This scope extends the public scope with people that have purchase the course
ES_PURCHASED = "Purchased"

#: This scope extends the public scope with people taking the course
#: to earn academic credit. They have probably paid money.
ES_CREDIT = "ForCredit"

#: This scope extends the ForCredit scope to be specific to people who
#: are engaged in a degree-seeking program.
ES_CREDIT_DEGREE = "ForCreditDegree"

#: This scope extends the ForCredit scope to be specific to people who
#: are taking the course for credit, but are not engaged in
#: seeking a degree.
ES_CREDIT_NONDEGREE = "ForCreditNonDegree"

from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

class ScopeTerm(SimpleTerm):

	def __init__(self, value, title=None, implies=(), implied_by=(), vendor_key=None, vendor_key_prefix=None):
		SimpleTerm.__init__(self, value, title=title)
		self.implies = implies
		self.implied_by = implied_by
		self.vendor_key = vendor_key if vendor_key else value
		self.vendor_key_prefix = vendor_key_prefix if vendor_key_prefix else value

ENROLLMENT_SCOPE_VOCABULARY = SimpleVocabulary(
	[ScopeTerm(ES_PUBLIC,
			   title=_('Open'),
			   implied_by=(ES_CREDIT, ES_CREDIT_DEGREE, ES_CREDIT_NONDEGREE, ES_PURCHASED),
			   vendor_key='Open',
			   vendor_key_prefix='Open'),
	 ScopeTerm(ES_PURCHASED,
				title=_('Purchased'),
				implies=(ES_PUBLIC,),
				implied_by=(ES_CREDIT, ES_CREDIT_DEGREE, ES_CREDIT_NONDEGREE)),
	 ScopeTerm(ES_CREDIT,
				title=_('For Credit'),
				implies=(ES_PUBLIC, ES_PURCHASED),
				implied_by=(ES_CREDIT_DEGREE, ES_CREDIT_NONDEGREE),
				vendor_key='In-Class',
				vendor_key_prefix='InClass'),
	 ScopeTerm(ES_CREDIT_DEGREE,
				title=_('For Credit (Degree)'),
				implies=(ES_CREDIT, ES_PURCHASED, ES_PUBLIC),
				implied_by=()),
	 ScopeTerm(ES_CREDIT_NONDEGREE,
				title=_('For Credit (Non-degree)'),
				implies=(ES_CREDIT, ES_PURCHASED, ES_PUBLIC),
				implied_by=())])

class ICourseInstanceEnrollmentRecordContainer(IContainer):
	"""
	The primary home of the enrollment records for a course.

	This should have the course in its lineage.
	"""

class ICourseInstanceEnrollmentRecord(ILastModified,
									  IContained):
	"""
	A record of enrollment in a particular course instance.
	Expect object added and removed events to be fired when
	people are enrolled and when people ar dropped as these
	objects are created and destroyed.
	"""

	containers(ICourseInstanceEnrollmentRecordContainer)
	__parent__.required = False

	CourseInstance = Object(ICourseInstance,
							title="The course instance",
							description="This should also be in the lineage of this object. "
							"This is to allow ObjectMovedEvents to be able to find both the current "
							"and previous course, given the current and previous parents",
							required=False)

	Principal = Object(interface.Interface,
					   title="The principal this record is for",
					   required=False)

	Scope = Choice(title="The name of the enrollment scope",
				   vocabulary=ENROLLMENT_SCOPE_VOCABULARY,
				   default=ES_PUBLIC)

class ICourseEnrollmentManager(interface.Interface):
	"""
	Something that manages the enrollments in an individual
	course. This is typically available as an adapter
	from :class:`.ICourseInstance`, or some course instances
	may choose to implement this directly.
	"""

	def enroll(principal, scope=ES_PUBLIC, context=None):
		"""
		Cause the given principal to be enrolled in this course, raising
		an appropriate error if that cannot be done.

		If the principal is already enrolled, this has no effect,
		regardless of scope.

		:keyword scope: One of the items from the :data:`.ENROLLMENT_SCOPE_VOCABULARY`
		:keyword context: Any information passed during record creation event

		:return: A truth value that is True if some action was taken,
			and false of no action was taken.
		"""

	def drop(principal):
		"""
		Cause the given principal to no longer be enrolled.

		If the given principal was not enrolled, this has no effect.

		:return: A truth value that is True if some action was taken,
			and false of no action was taken.
		"""

	def drop_all():
		"""
		Cause all the enrolled principals to be removed.
		This can be faster and safer than trying to remove all
		the records individually manually.

		:return: A list of the enrollment records removed.
		"""

class IPrincipalEnrollments(interface.Interface):
	"""
	Something that can list the enrollments of an individual
	user (contrast with :class:`.ICourseEnrollments`).

	In the case that there might be multiple sources of enrollment
	data managing different parts of the system, such as during
	transition times, we expect that these will be registered as
	subscribers providing this interface and requiring an
	:class:`.IPrincipal` or :class:`.IUser`.`

	This is an evolving interface; currently we expect
	that specialized versions will be provided tailored to specific consumers.
	"""

	def iter_enrollments():
		"""
		Iterate across enrollment information for the context.
		"""

class ICourseEnrollments(interface.Interface):
	"""
	Something that can list the enrollments of an individual
	course (contrast with :class:`.IPrincipalEnrollments`).

	This is an evolving interface; currently we expect
	that specialized versions will be provided tailored to specific consumers.
	"""

	def iter_principals():
		"""
		Iterate across principal names information for the context.
		"""
	
	def iter_enrollments():
		"""
		Iterate across enrollment information for the context.
		"""

	def count_enrollments():
		"""
		Return the number of students enrolled in the context.
		This may be more efficient than iterating all enrollments.
		"""

	def get_enrollment_for_principal(principal):
		"""
		Given the same kind of principal that was enrolled
		with the course enrollment manager, return
		the enrollment record for that principal.

		If the principal is not enrolled, return None.
		"""

class IEnrollmentException(interface.Interface):
	"""
	marker interface for enrollment exception"
	"""

@interface.implementer(IEnrollmentException)
class AlreadyEnrolledException(ValueError):
	pass

from zope.interface.interfaces import ObjectEvent
from zope.interface.interfaces import IObjectEvent

class ICourseInstanceAvailableEvent(IObjectEvent):
	"""
	An event that is sent, usually during startup or synchronization,
	to notify that a course instance has been setup by this package.
	This is a hook for additional packages to perform any setup they
	need to do, such as synchronizing database state with course
	content state.
	"""

@interface.implementer(ICourseInstanceAvailableEvent)
class CourseInstanceAvailableEvent(ObjectEvent):
	pass

from zope.lifecycleevent import ObjectCreatedEvent
from zope.lifecycleevent.interfaces import IObjectCreatedEvent

class ICourseInstanceEnrollmentRecordCreatedEvent(IObjectCreatedEvent):
	"""
	An event that is sent during the creation of a
	:class:`.ICourseInstanceEnrollmentRecord`.
	The context it's any information subscribers may be interested in
	"""
	context = interface.Attribute("Creationg context information")

@interface.implementer(ICourseInstanceEnrollmentRecordCreatedEvent)
class CourseInstanceEnrollmentRecordCreatedEvent(ObjectCreatedEvent):

	def __init__(self, obj, context=None):
		super(CourseInstanceEnrollmentRecordCreatedEvent, self).__init__(obj)
		self.context = context

#### Back to discussions

class ICourseInstancePublicScopedForum(ICourseInstanceScopedForum):

	SharingScopeName = ValidTextLine(description="Should be the same as ES_PUBLIC",
									 required=False,
									 default=ES_PUBLIC)
	SharingScopeName.setTaggedValue('value', ES_PUBLIC)

class ICourseInstanceForCreditScopedForum(ICourseInstanceScopedForum):
	"""
	A forum intended to be visible to those enrolled for credit.
	"""

	SharingScopeName = ValidTextLine(description="Should be the same as ES_CREDIT",
									 required=False,
									 default=ES_CREDIT)
	SharingScopeName.setTaggedValue('value', ES_CREDIT)

class ICourseInstancePurchasedScopedForum(ICourseInstanceScopedForum):
	"""
	A forum intended to be visible to those who have purchased a course.
	"""

	SharingScopeName = ValidTextLine(description="Should be the same as ES_PURCHASED",
									 required=False,
									 default=ES_PURCHASED)
	SharingScopeName.setTaggedValue('value', ES_PURCHASED)

###
# Policies
###

class ICourseGradingPolicy(IContained, ILastModified):
	"""
	A marker interface to store a course grading policy
	"""
	
	def validate():
		"""
		validate this policy
		"""
		
	def synchronize():
		"""
		Perform any adjustment of this policy during course synchronization
		"""
		
	def grade(principal):
		"""
		return the [current] grade for the specified user/principal
		"""
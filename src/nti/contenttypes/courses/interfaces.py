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

from zope import interface

from zope.security.interfaces import IPrincipal

from zope.site.interfaces import IFolder

from zope.container.interfaces import IOrderedContainer
from zope.container.interfaces import IContainerNamesContainer

from zope.container.constraints import contains
from zope.container.constraints import containers

from nti.dataserver.interfaces import IShouldHaveTraversablePath
from nti.dataserver.interfaces import ITitledDescribedContent
from nti.dataserver.interfaces import ILastModified

from nti.dataserver.contenttypes.forums import interfaces as frm_interfaces

from nti.utils import schema
from nti.ntiids.schema import ValidNTIID

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

	src = schema.ValidTextLine(title="json file to populate the node overview",
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

	AvailableBeginning = schema.ValidDatetime(
		title="This node is available, or expected to be entered or active at this time",
		description="""When present, this specifies the time instant at which
		this node and its children are to be available or active. If this is absent,
		it is always available or active. While this is represented here as an actual
		concrete timestamp, it is expected that in many cases the source representation
		will be relative to something else (a ``timedelta``) and conversion to absolute
		timestamp will be done as needed.""",
		required=False)

	AvailableEnding = schema.ValidDatetime(
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

class ICourseInstance(IFolder,
					  IShouldHaveTraversablePath,
					  _ICourseOutlineNodeContainer):
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
	"""

	containers(ICourseAdministrativeLevel)
	__parent__.required = False

	Discussions = schema.Object(frm_interfaces.IBoard,
								title="The root discussion board for this course.",
								description="Typically, courses will 'contain' their own discussions, "
								"but this may be a reference to another object.")

	Outline = schema.Object(ICourseOutline,
							title="The course outline or syllabus, if there is one.",
							required=False)

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
	# edit them through-the-web
	instructors = schema.UniqueIterable(title="The principals that are the intsructors of the course.",
										description="They get special access rights.",
										value_type=schema.Object(IPrincipal))

from pyramid.traversal import lineage as _lineage

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
	for x in _lineage(context):
		course = ICourseInstance(x, None)
		if course is not None:
			break

	if course is None:
		return False

	return any((username == instructor.id for instructor in course.instructors))


class ICourseEnrollmentManager(interface.Interface):
	"""
	Something that manages the enrollments in an individual
	course. This is typically registered as an adapter
	from :class:`.ICourseInstance`, or some course instances
	may choose to implement this directly.
	"""

	def enroll(principal):
		"""
		Cause the given principal to be enrolled in this course, raising
		an appropriate error if that cannot be done.

		If the principal is already enrolled, this has no effect.

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

	def iter_enrollments():
		"""
		Iterate across enrollment information for the context.
		"""

	def count_enrollments():
		"""
		Return the number of students enrolled in the context.
		This may be more efficient than iterating all enrollments.
		"""

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Course-related interfaces.

Most course-related objects are also folders containing
subobjects, and they are also :class:`.IPossibleSite` objects
for local policy containment (including things like default
preferences). The expected contents of each type of object
are explained on the object itself.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.site.interfaces import IFolder
from zope.container.constraints import contains
from zope.container.constraints import containers

from nti.dataserver.contenttypes.forums import interfaces as frm_interfaces

from nti.utils import schema

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
#     means ACLs and "effective principals" get involved.
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

	contains(b'.ICourseInstance', b'.ICourseAdministrativeLevel')


class ICourseInstance(IFolder):
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

	Discussions = schema.Object(frm_interfaces.IBoard,
								title="The root discussion board for this course.")

class IPrincipalEnrollments(interface.Interface):
	"""
	Something that can list the enrollments of an individual
	user.

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

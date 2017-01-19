#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ACL providers for course data.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.authentication.interfaces import IUnauthenticatedPrincipal

from zope.security.interfaces import IPrincipal

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceBoard
from nti.contenttypes.courses.interfaces import ICourseInstanceForum
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance

from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CREATE
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ACT_SYNC_LIBRARY
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import ace_denying
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.contenttypes.forums.acl import CommunityBoardACLProvider
from nti.dataserver.contenttypes.forums.acl import CommunityForumACLProvider

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.interfaces import EVERYONE_GROUP_NAME
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.interfaces import IACLProvider

from nti.property.property import Lazy

from nti.traversal.traversal import find_interface


@component.adapter(ICourseInstance)
@interface.implementer(IACLProvider)
class CourseInstanceACLProvider(object):
    """
    Provides the basic ACL for a course instance.

    This cooperates with the course's principal map to provide
    the full access control.

    We typically expect the course catalog entry for this object
    to be a child and inherit the same ACL.
    """

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        # See comments in nti.dataserver.authorization_acl:has_permission
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        course = self.context
        sharing_scopes = course.SharingScopes
        sharing_scopes.initScopes()

        aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
                ace_allowing(ROLE_CONTENT_ADMIN, ACT_READ, type(self)),
                ace_allowing(ROLE_CONTENT_ADMIN, ACT_CONTENT_EDIT, type(self)),
                ace_allowing(ROLE_CONTENT_ADMIN, ACT_SYNC_LIBRARY, type(self))]

        # Anyone still enrolled in course has access, whether the course
        # is public or not.
        public_scope = sharing_scopes[ES_PUBLIC]
        aces.append(ace_allowing(IPrincipal(public_scope),
                                 ACT_READ, 
                                 type(self)))

        # Courses marked as being anonymously accessible should have READ access
        # for the unauthenticated user.  Note that for BWC we intentionally
        # do NOT use the Everyone principal.  We don't want authenticated
        # but unenrolled users to have access right now.
        if IAnonymouslyAccessibleCourseInstance.providedBy(course):
            u_principal = component.getUtility(IUnauthenticatedPrincipal)
            aces.append(ace_allowing(u_principal,
                                     ACT_READ,
                                     type(self)))

        for i in course.instructors or ():
            aces.append(ace_allowing(i, ACT_READ, type(self)))

        # JZ: 2015-01-11 Subinstance instructors get the same permissions
        # as their students.
        for subinstance in get_course_subinstances(course):
            aces.extend(ace_allowing(i, ACT_READ, type(self))
                        for i in subinstance.instructors or ())

        # Now our content editors/admins.
        for editor in get_course_editors(course):
            aces.append(ace_allowing(editor, ACT_READ, type(self)))
            aces.append(ace_allowing(editor, ACT_UPDATE, type(self)))
            aces.append(ace_allowing(editor, ACT_CONTENT_EDIT, type(self)))

        result = acl_from_aces(aces)
        return result


@interface.implementer(IACLProvider)
@component.adapter(ICourseCatalogEntry)
class CourseCatalogEntryACLProvider(object):
    """
    Provides the ACL for course catalog entries.
    """

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        # See comments in nti.dataserver.authorization_acl:has_permission
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        cce = self.context
        # catalog entries can be non-public children of public courses,
        # or public children of non-public courses.
        non_public = find_interface(cce,
                                    INonPublicCourseInstance,
                                    strict=False)

        if non_public:
            # Ok, was that us, or are we not non-public and our direct parent
            # is also not non-public?
            if     INonPublicCourseInstance.providedBy(self.context) \
                or INonPublicCourseInstance.providedBy(self.__parent__):
                non_public = True
            else:
                # We don't directly provide it, neither does our parent, so
                # we actually want to be public and not inherit this.
                non_public = False

        acl = []
        if non_public:
            # Although it might be be nice to inherit from the non-public
            # course in our lineage, we actually need to be a bit stricter
            # than that...the course cannot forbid creation or do a deny-all
            # (?)
            course_in_lineage = find_interface(cce, 
                                               ICourseInstance, 
                                               strict=False)

            # Do we have a course instance? If it's not in our lineage its the legacy
            # case
            course = course_in_lineage or ICourseInstance(cce, None)
            if course is not None:
                # Use our course ACL to give enrolled students access.
                acl.extend(IACLProvider(course).__acl__)
                acl.append(
                    # Nobody can 'create' (enroll)
                    # Nobody else can view it either
                    ace_denying(IPrincipal(AUTHENTICATED_GROUP_NAME),
                                (ACT_CREATE, ACT_READ),
                                CourseCatalogEntryACLProvider),
                )
                acl.append(
                    # use both everyone and authenticated for
                    # belt-and-suspenders
                    ace_denying(IPrincipal(EVERYONE_GROUP_NAME),
                                (ACT_CREATE, ACT_READ),
                                CourseCatalogEntryACLProvider),
                )
            else:
                # Hmm.
                acl.append(ACE_DENY_ALL)
        else:
            acl.append(ace_allowing(IPrincipal(AUTHENTICATED_GROUP_NAME),
                                    (ACT_CREATE, ACT_READ),
                                    CourseCatalogEntryACLProvider))
        acl = acl_from_aces(acl)
        return acl


@component.adapter(ICourseOutlineNode)
@interface.implementer(IACLProvider)
class CourseOutlineNodeACLProvider(object):
    """
    Provides the basic ACL for a course outline.
    """

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        # See comments in nti.dataserver.authorization_acl:has_permission
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, self),
                ace_allowing(ROLE_CONTENT_ADMIN, ALL_PERMISSIONS, type(self))]
        course = find_interface(self.context, ICourseInstance, strict=False)
        if course is not None:
            # give editors special powers
            aces.extend(ace_allowing(i, ALL_PERMISSIONS, type(self))
                        for i in get_course_editors(course) or ())
        result = acl_from_aces(aces)
        return result


@component.adapter(ICourseInstanceBoard)
@interface.implementer(IACLProvider)
class CourseBoardACLProvider(CommunityBoardACLProvider):
    """
    Plug in our editors to have READ access to the boards.
    We deny all up the chain.
    """

    def _extend_acl_after_creator_and_sharing(self, acl):
        super(CourseBoardACLProvider,
              self)._extend_acl_after_creator_and_sharing(acl)
        course = find_interface(self.context, ICourseInstance, strict=False)
        if course is None:
            __traceback_info__ = self.context
            raise TypeError(
                "Not enough context information to get all parents")
        for editor in get_course_editors(course):
            acl.append(ace_allowing(editor, ACT_READ, type(self)))


@component.adapter(ICourseInstanceForum)
@interface.implementer(IACLProvider)
class CourseForumACLProvider(CommunityForumACLProvider):
    """
    Plug in our editors to have READ access to the forums.
    """

    def _extend_acl_after_creator_and_sharing(self, acl):
        super(CourseForumACLProvider,
              self)._extend_acl_after_creator_and_sharing(acl)
        course = find_interface(self.context, ICourseInstance)
        for editor in get_course_editors(course):
            acl.append(ace_allowing(editor, ACT_READ, type(self)))
            # Since we do not deny-all in chain, we need to
            # explicitly restrict access for editors
            acl.append(ace_denying(editor,
                                   (ACT_CONTENT_EDIT, ACT_UPDATE),
                                   type(self)))

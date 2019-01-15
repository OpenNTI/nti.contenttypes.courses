#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ACL providers for course data.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.authentication.interfaces import IUnauthenticatedPrincipal

from zope.cachedescriptors.property import Lazy

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import IRolePermissionManager
from zope.securitypolicy.rolepermission import RolePermissionManager

from nti.contentlibrary.interfaces import IRenderableContentPackage

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceBoard
from nti.contenttypes.courses.interfaces import ICourseInstanceForum
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceScopedForum

from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_course_instructors
from nti.contenttypes.courses.utils import get_course_hierarchy
from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import get_content_unit_courses

from nti.contenttypes.courses.discussions.utils import get_forum_scopes

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CREATE
from nti.dataserver.authorization import ACT_DELETE
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ROLE_SITE_ADMIN
from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ACT_SYNC_LIBRARY
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import ace_denying
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.contenttypes.forums.acl import CommunityBoardACLProvider
from nti.dataserver.contenttypes.forums.acl import _ACLCommunityForumACLProvider

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ISupplementalACLProvider

from nti.externalization.persistence import NoPickle

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface
from nti.app.authentication import get_remote_user

logger = __import__('logging').getLogger(__name__)


def editor_aces_for_course(course, provider):
    """
    Gather the editor aces for a given course.
    """
    aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(provider)),
            ace_allowing(ROLE_CONTENT_ADMIN, ACT_READ, type(provider)),
            ace_allowing(ROLE_CONTENT_ADMIN, ACT_CONTENT_EDIT, type(provider)),
            ace_allowing(ROLE_CONTENT_ADMIN, ACT_SYNC_LIBRARY, type(provider)),
            ace_allowing(ROLE_SITE_ADMIN, ACT_READ, type(provider)),
            ace_allowing(ROLE_SITE_ADMIN, ACT_CONTENT_EDIT, type(provider))]

    # Now our content editors/admins.
    for editor in get_course_editors(course):
        aces.append(ace_allowing(editor, ACT_READ, type(provider)))
        aces.append(ace_allowing(editor, ACT_UPDATE, type(provider)))
        aces.append(ace_allowing(editor, ACT_CONTENT_EDIT, type(provider)))
    return aces


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
        aces = editor_aces_for_course(course, self)

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
        non_public = find_interface(cce, INonPublicCourseInstance, strict=False)
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

        # Although it might be be nice to inherit from the non-public
        # course in our lineage, we actually need to be a bit stricter
        # than that...the course cannot forbid creation or do a deny-all
        # (?)
        course = find_interface(cce, ICourseInstance, strict=False)
        # Do we have a course instance? If it's not in our lineage its the legacy
        # case
        course = course or ICourseInstance(cce, None)
        if course is not None:
            # Use our course ACL to give enrolled students access.
            acl.extend(IACLProvider(course).__acl__)
            if not non_public:
                if not cce.AvailableToEntityNTIIDs:
                    acl.append(ace_allowing(IPrincipal(AUTHENTICATED_GROUP_NAME),
                                            (ACT_CREATE, ACT_READ),
                                            CourseCatalogEntryACLProvider))
                else:
                    # This catalog entry is setup to restrict enrollment visibility to
                    # a set of entities.
                    # Set to non_public restricts access for this field too.
                    for enrollment_entity_ntiid in cce.AvailableToEntityNTIIDs:
                        entity = find_object_with_ntiid(enrollment_entity_ntiid)
                        if entity is not None:
                            acl.append(ace_allowing(IPrincipal(entity),
                                                    (ACT_CREATE, ACT_READ),
                                                    CourseCatalogEntryACLProvider))
        acl.append(ACE_DENY_ALL)
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
        super(CourseBoardACLProvider, self)._extend_acl_after_creator_and_sharing(acl)
        course = find_interface(self.context, ICourseInstance, strict=False)
        if course is None:
            # pylint: disable=unused-variable
            __traceback_info__ = self.context
            raise TypeError("Not enough context information to get all parents")

        # Editors, Instructors, and Global content admins get read and create
        for editor in get_course_editors(course):
            acl.append(ace_allowing(editor, (ACT_READ, ACT_CREATE), type(self)))
        for inst in get_course_instructors(course):
            acl.append(ace_allowing(inst, (ACT_READ, ACT_CREATE), type(self)))
        acl.append(ace_allowing(ROLE_CONTENT_ADMIN, (ACT_READ, ACT_CREATE), type(self)))


class AbstractCourseForumACLProvider(_ACLCommunityForumACLProvider):
    """
    An abstract ACLProvider for ICourseInstanceForums. Note we extend _ACLCommunityForumACLProvider
    as there are legacy "ICourseInstanceForum" that aren't actually beneath an ICourseInstanceBoard
    and ICourseInstance.  The dynamic acl generation breaks down in that case so our superclass
    handles using the static persistent ACLs on those forums when necessary.

    In general ICourseInstanceForums are created by a course scope.  Usually this is the public
    scope but in some cases of ICourseInstanceScopedForums this may be a different scope. Members of the
    applicable sharing scope typically have read access. Instructors and Editors have elevated permissions.

    Admins also have elevated permissions by default.
    """

    _PERMS_FOR_SHARING_TARGETS = (ACT_READ, )
    _PERMS_FOR_CREATOR = ()
    _DENY_ALL = True

    def _sharing_scopes(self):
        """
        By default treat these forums as being shared with everyone in the course
        """
        return (ES_PUBLIC, )

    def _get_sharing_target_names(self):
        course = find_interface(self.context, ICourseInstance)
        scopes = self._sharing_scopes()
        return [course.SharingScopes[scope] for scope in scopes if scope in course.SharingScopes]

    def _adjust_acl_for_inst(self, acl, inst):
        pass

    def _adjust_acl_for_editor(self, acl, editor):
        pass

    def _extend_acl_after_creator_and_sharing(self, acl):
        super(AbstractCourseForumACLProvider, self)._extend_acl_after_creator_and_sharing(acl)

        course = find_interface(self.context, ICourseInstance)
        if course is None:
            return  # Legacy community based courses

        for inst in get_course_instructors(course):
            self._adjust_acl_for_inst(acl, inst)
        for editor in get_course_editors(course):
            self._adjust_acl_for_editor(acl, editor)
        # Make sure content admins behave like course editors
        self._adjust_acl_for_editor(acl, ROLE_CONTENT_ADMIN)
        self._extend_with_admin_privs(acl)


@component.adapter(ICourseInstanceForum)
@interface.implementer(IACLProvider)
class CourseForumACLProvider(AbstractCourseForumACLProvider):
    """
    Basic ICourseInstanceForums grant the sharing target read and create.  That is
    members of that scope can both see the forum and create new topics beneath it.

    Instructors have elevated permissions allowing them to edit and delete.  Editors
    also have those eleveated permissions but they can only delete if there are no
    topics created beneath the forums. (This editor/instructor difference makes sense now,
    but it seems like we may want to lift or unify that and move to a mark as deleted).
    """

    _PERMS_FOR_SHARING_TARGETS = (ACT_READ, ACT_CREATE, )

    def _adjust_acl_for_inst(self, acl, inst):
        acl.append(ace_allowing(inst, ALL_PERMISSIONS, type(self)))

    def _adjust_acl_for_editor(self, acl, editor):
        if len(self.context) > 0:
            acl.append(ace_denying(editor, ACT_DELETE, type(self)))
        acl.append(ace_allowing(editor, ALL_PERMISSIONS, type(self)))


@component.adapter(ICourseInstanceScopedForum)
@interface.implementer(IACLProvider)
class CourseScopeForumACLProvider(AbstractCourseForumACLProvider):
    """
    ICourseInstanceScopedForums restrict the sharing scopes with access to the scope
    represented by the forum itself.  These forums typcially hold the system managed
    course topics and as such we don't allow the creation of topics beneath them by students,
    nor do we allow the deletion of topics. This is a bit of an abuse but it keeps behaviour
    sane and consistent until the auto generated topics are tagged approrpiately so that their
    acls can be handled seperately.
    """

    def _sharing_scopes(self):
        return get_forum_scopes(self.context)

    def _adjust_acl_for_editor(self, acl, editor):
        acl.append(ace_allowing(editor, (ACT_READ, ACT_CREATE, ), type(self)))

    def _adjust_acl_for_inst(self, acl, inst):
        acl.append(ace_allowing(inst, (ACT_READ, ACT_CREATE, ), type(self)))


@component.adapter(ICourseInstanceScopedForum)
@interface.implementer(IRolePermissionManager)
@NoPickle
class CourseScopeForumRolePermissionManager(RolePermissionManager):
    """
    A zope security policy role permission manager that denies DELETE
    for the site admin role.  site admin role has all permissions on the
    root site folder so we must deny that here to prevent them from
    deleting course managed discussions.
    """

    def __init__(self, forum):
        super(CourseScopeForumRolePermissionManager, self).__init__()
        self.denyPermissionToRole(ACT_DELETE.id, ROLE_SITE_ADMIN.id)


@component.adapter(IRenderableContentPackage)
@interface.implementer(ISupplementalACLProvider)
class RenderableContentPackageSupplementalACLProvider(object):
    """
    Supplement :class:`IRenderableContentPackage` objects with
    the acl of all courses containing these packages. If unpublished,
    only course editors have access.
    """

    def __init__(self, context):
        self.context = context

    def _get_courses(self):
        """
        Get all courses and subinstances that contain this package.
        """
        result = set()
        package = self.context
        seen_set = set()
        remote_user = get_remote_user()
        if getattr(remote_user, 'username', '') == 'student1':
            from IPython.terminal.debugger import set_trace;set_trace()
        courses = get_content_unit_courses(package)
        for course in courses or ():
            if course in seen_set:
                continue
            seen_set.add(course)
            course_tree = get_course_hierarchy(course)
            for instance in course_tree or ():
                if      instance in seen_set \
                    and instance != course:
                    continue
                seen_set.add(instance)
                course_packages = get_course_packages(instance)
                if package in course_packages:
                    result.add(instance)
        return result

    @Lazy
    def __acl__(self):
        result = []
        is_published = self.context.is_published()
        courses = self._get_courses()
        for course in courses:
            if is_published:
                # If published, we want the whole ACL
                # Shoudl we eliminate dupes?
                course_acl = IACLProvider(course).__acl__
                result.extend(course_acl)
            else:
                # Otherwise, fetch just the course editors
                aces = editor_aces_for_course(course, self)
                result.extend(aces)
        return acl_from_aces(result)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceForum
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import ICourseInstanceScopedForum
from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope

from nti.contenttypes.courses.legacy_catalog import ICourseCatalogInstructorLegacyInfo

from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface


LINKS = StandardExternalFields.LINKS
MIMETYPE = StandardExternalFields.MIMETYPE

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseOutlineNode)
@interface.implementer(IExternalObjectDecorator)
class _CourseOutlineNodeDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        if not original.LessonOverviewNTIID:
            external.pop('LessonOverviewNTIID', None)
        if 'ntiid' not in external and getattr(original, 'ntiid', None):
            external['ntiid'] = original.ntiid


@component.adapter(ICourseInstanceForum)
@interface.implementer(IExternalObjectDecorator)
class _CourseInstanceForumDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        if not ICourseInstanceScopedForum.providedBy(original):
            course = find_interface(original, ICourseInstance, strict=False)
            if course is not None:
                public_scope = course.SharingScopes[ES_PUBLIC]
                external['DefaultSharedToNTIIDs'] = [public_scope.NTIID]


@component.adapter(ITopic)
@interface.implementer(IExternalObjectDecorator)
class _CourseInstanceForumTopicDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        forum = original.__parent__
        if not ICourseInstanceScopedForum.providedBy(forum):
            course = find_interface(original, ICourseInstance, strict=False)
            if course is not None:
                public_scope = course.SharingScopes[ES_PUBLIC]
                external['ContainerDefaultSharedToNTIIDs'] = [public_scope.NTIID]


@component.adapter(ICourseOutline)
@interface.implementer(IExternalObjectDecorator)
class _CourseOutlineDecorator(Singleton):

    def decorateExternalObject(self, unused_original, external):
        external.pop('publishEnding', None)
        external.pop('publishBeginning', None)


@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseCatalogInstructorLegacyInfo)
class _InstructorLegacyInfoDecorator(Singleton):

    def decorateExternalObject(self, unused_original, external):
        external.pop('userid', None)


@component.adapter(ICourseInstanceSharingScope)
@interface.implementer(IExternalObjectDecorator)
class _CourseInstanceSharingScopeDecorator(Singleton):

    def decorateExternalObject(self, scope, external):
        # Warning !!! For BWC w/ clients
        external[MIMETYPE] = 'application/vnd.nextthought.community'

        course = find_interface(scope, ICourseInstance, strict=False)
        if course is None:
            return
        _links = external.setdefault(LINKS, [])
        link = Link(course,
                    rel='CourseInstance')
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = scope
        _links.append(link)

        # Update scope alias with entry title
        friendly_named = IFriendlyNamed(scope)
        if friendly_named.alias is None:
            # Override our externalized alias with our course title
            # All entity objects default this via the alias or realname or
            # username.
            entry = ICourseCatalogEntry(course, None)
            title = getattr(entry, 'title', None)
            if title:
                scope_name = scope.__name__
                alias = title if scope_name == ES_PUBLIC else '%s (%s)' % (title, scope_name)
                external['alias'] = alias


@interface.implementer(IExternalObjectDecorator)
class _CourseNonPublicStatusDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        if 'is_non_public' not in external:
            is_non_public = INonPublicCourseInstance.providedBy(original)
            external['is_non_public'] = is_non_public


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _CourseAdminLevelDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        course = ICourseInstance(original, None)
        if course is not None:
            admin = find_interface(course, ICourseAdministrativeLevel, strict=False)
            if admin is not None:
                external['AdminLevel'] = admin.__name__


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _CourseSiteDecorator(Singleton):

    def decorateExternalObject(self, original, external):
        course = ICourseInstance(original, None)
        if course is not None:
            site = find_interface(course, IHostPolicyFolder, strict=False)
            if site is not None:
                external['Site'] = site.__name__


@component.adapter(ICourseContentPackageBundle)
@interface.implementer(IExternalObjectDecorator)
class _CourseBundleDecorator(Singleton):
    """
    The client apparently uses the bundle title as a proxy to the course title.
    With edits, these may fall out of sync. Should we always overwrite?
    """

    def decorateExternalObject(self, original, external):
        title = external['title']
        if not title:
            course = ICourseInstance(original, None)
            entry = ICourseCatalogEntry(course, None)
            entry_title = getattr(entry, 'title', '')
            if entry_title:
                external['title'] = entry_title

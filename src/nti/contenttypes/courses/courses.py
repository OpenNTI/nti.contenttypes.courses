#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from ExtensionClass import Base

from zope import interface

from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy
from zope.cachedescriptors.property import readproperty

from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeFolder
from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.contenttypes.courses import MessageFactory as _

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstances
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IContentCourseInstance
from nti.contenttypes.courses.interfaces import IContentCourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel

from nti.contenttypes.courses.forum import CourseInstanceBoard

from nti.contenttypes.courses.outlines import CourseOutline

from nti.contenttypes.courses.sharing import CourseInstanceSharingScopes
from nti.contenttypes.courses.sharing import CourseSubInstanceSharingScopes

from nti.ntiids.oids import to_external_ntiid_oid

from nti.schema.fieldproperty import createDirectFieldProperties

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseAdministrativeLevel)
class CourseAdministrativeLevel(CaseInsensitiveCheckingLastModifiedBTreeFolder):
    mime_type = mimeType = 'application/vnd.nextthought.courses.coursedaministrativelevel'


@interface.implementer(ICourseSubInstances)
class CourseSubInstances(CaseInsensitiveCheckingLastModifiedBTreeContainer):
    pass

@interface.implementer(ICourseInstance)
class CourseInstance(CaseInsensitiveCheckingLastModifiedBTreeFolder, Base):
    __external_can_create__ = False
    createDirectFieldProperties(ICourseInstance)

    lastSynchronized = 0

    def __init__(self):
        super(CourseInstance, self).__init__()

    # Whether or not they have contents, they are true
    def __bool__(self):
        return True
    __nonzero__ = __bool__

    @property
    def ntiid(self):
        return to_external_ntiid_oid(self)

    @ntiid.setter
    def ntiid(self, nv):
        pass

    @Lazy
    def Discussions(self):
        self._p_changed = True
        # Store it inside this folder
        # so it is traversable
        # TODO: Title
        # Course instance boards are a type-of
        # community board, and community boards
        # must be created by a community. We choose
        # the public scope.
        scopes = self.SharingScopes
        scopes.initScopes()
        public_scope = scopes[ES_PUBLIC]

        board = CourseInstanceBoard()
        board.creator = public_scope
        board.title = _('Discussions')
        lifecycleevent.created(board)
        self['Discussions'] = board
        return board

    def _delete_Outline(self):
        result = False
        for m in (self.__dict__, self):
            try:
                del m['Outline']
                result = True
            except KeyError:
                pass
        return result

    def _make_Outline(self):
        """
        A lazy helper to create this object's Outline.
        """
        # As per Discussions
        self._p_changed = True
        outline = CourseOutline()
        lifecycleevent.created(outline)
        try:
            self['Outline'] = outline
        except KeyError:
            logger.error("Cannot set outline for %s", self.__name__)
            raise
        return outline
    Outline = Lazy(_make_Outline, str('Outline'))

    @Lazy
    def SharingScopes(self):
        # As per Discussions
        self._p_changed = True
        scopes = self._make_sharing_scopes()
        lifecycleevent.created(scopes)
        self['SharingScopes'] = scopes
        return scopes

    def _make_sharing_scopes(self):
        return CourseInstanceSharingScopes()

    @Lazy
    def SubInstances(self):
        # As per Discussions
        self._p_changed = True
        folder = CourseSubInstances()
        lifecycleevent.created(folder)
        self['SubInstances'] = folder
        return folder

    @readproperty
    def instructors(self):
        return ()

    @property
    def links(self):
        return self._make_links()

    @property
    def title(self):
        entry = ICourseCatalogEntry(self, None)
        return getattr(entry, 'title', None)

    def _make_links(self):
        """
        Subclasses can extend this to customize the available links.

        """
        return ()

    def sublocations(self):
        """
        The order of SubInstances and SharingScopes matters, we have an ObjectRemovedEvent subscriber in which when
        a parent course is being removed and its child course has different instructors, it would remove access to the
        parent course for the instructors of child course which requires the intid of the SharingScopes of parent course.
        See subscriber 'on_course_instance_removed' in nti/contenttypes/courses/subscribers.py
        """
        _order_matters = (u'SubInstances', u'SharingScopes')
        for key in _order_matters:
            if key in self:
                yield self[key]

        for key in self:
            if key not in _order_matters:
                yield self[key]


from Acquisition import aq_acquire

from nti.contentlibrary.presentationresource import DisplayableContentMixin


@interface.implementer(IContentCourseInstance)
class ContentCourseInstance(DisplayableContentMixin,
                            CourseInstance):

    __external_class_name__ = 'CourseInstance'
    createDirectFieldProperties(IContentCourseInstance)

    @property
    def PlatformPresentationResources(self):
        """
        If we do not have our own presentation resources, look in our bundle.
        """

        ours = super(ContentCourseInstance, self).PlatformPresentationResources
        if ours:
            return ours

        if self.ContentPackageBundle:
            # We always want to check bundle, even if the root is the same,
            # because we may need to look at the package level.
            return self.ContentPackageBundle.PlatformPresentationResources

@interface.implementer(IContentCourseSubInstance)
class ContentCourseSubInstance(ContentCourseInstance):

    def __getattr__(self, name):
        if name.startswith('_'):
            # TODO: would really like to use the actual
            # acquisition policy
            raise AttributeError(name)
        return aq_acquire(self.__parent__, name)

    def _make_sharing_scopes(self):
        return CourseSubInstanceSharingScopes()

    @property
    def ContentPackageBundle(self):
        """
        Our content package bundle is always acquired
        """
        try:
            return aq_acquire(self.__parent__, 'ContentPackageBundle')
        except AttributeError:
            return None

    def prepare_own_outline(self):
        self._p_activate()
        if 'Outline' not in self.__dict__:
            outline = self._make_Outline()
            self.__dict__['Outline'] = outline

    def _get_Outline(self):
        self._p_activate()
        if 'Outline' in self.__dict__:
            return self.__dict__['Outline']
        return aq_acquire(self.__parent__, 'Outline').__of__(self)

    def _set_Outline(self, outline):
        self._p_activate()
        self._p_changed = True
        self.__dict__['Outline'] = outline

    def _del_Outline(self):
        self._p_activate()
        if 'Outline' in self.__dict__:
            self._p_changed = True
            del self.__dict__['Outline']

    Outline = property(_get_Outline, _set_Outline, _del_Outline)

    # The original impetus says that they all get separate forums

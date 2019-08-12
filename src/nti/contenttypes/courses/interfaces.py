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

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class,no-value-for-parameter
# pylint: disable=locally-disabled,too-many-ancestors,no-self-argument

from z3c.schema.email import isValidMailAddress

from zope import component
from zope import interface

from zope.annotation.interfaces import IAttributeAnnotatable

from zope.container.constraints import contains
from zope.container.constraints import containers

from zope.container.interfaces import IContainer
from zope.container.interfaces import IContained
from zope.container.interfaces import IContentContainer
from zope.container.interfaces import IOrderedContainer
from zope.container.interfaces import IContainerNamesContainer

from zope.interface.common.mapping import IEnumerableMapping
from zope.interface.common.mapping import IExtendedWriteMapping

from zope.interface.common.sequence import ISequence

from zope.interface.interfaces import IMethod
from zope.interface.interfaces import ObjectEvent
from zope.interface.interfaces import IObjectEvent

from zope.lifecycleevent import ObjectCreatedEvent
from zope.lifecycleevent.interfaces import IObjectCreatedEvent

from zope.schema import ValidationError

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import IRolePermissionManager

from zope.site.interfaces import IFolder

from nti.cabinet.interfaces import ISourceFiler

from nti.contentfragments.schema import PlainTextLine
from nti.contentfragments.schema import HTMLContentFragment

from nti.contentlibrary.interfaces import IDisplayableContent
from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import ISynchronizationParams
from nti.contentlibrary.interfaces import ISynchronizationResults
from nti.contentlibrary.interfaces import IDelimitedHierarchyBucket
from nti.contentlibrary.interfaces import IEditableContentPackageBundle
from nti.contentlibrary.interfaces import IGenericSynchronizationResults
from nti.contentlibrary.interfaces import IEnumerableDelimitedHierarchyBucket

from nti.contenttypes.completion.interfaces import ICompletionContext

from nti.contenttypes.courses import MessageFactory as _

from nti.contenttypes.credit.interfaces import IAwardedCredit
from nti.contenttypes.credit.interfaces import IAwardableCredit
from nti.contenttypes.credit.interfaces import IAwardableCreditContext

from nti.contenttypes.reports.interfaces import IReportContext

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import InvalidData
from nti.dataserver.interfaces import ILastModified
from nti.dataserver.interfaces import IGrantAccessException
from nti.dataserver.interfaces import ITitledDescribedContent
from nti.dataserver.interfaces import IShouldHaveTraversablePath
from nti.dataserver.interfaces import IUseNTIIDAsExternalUsername

from nti.dataserver.contenttypes.forums.interfaces import IBoard
from nti.dataserver.contenttypes.forums.interfaces import IDefaultForumBoard

from nti.dataserver.users.interfaces import IDisallowMembershipOperations

from nti.invitations.interfaces import IUserInvitation
from nti.invitations.interfaces import IInvitationActor

from nti.ntiids.schema import ValidNTIID

from nti.property.property import alias

from nti.publishing.interfaces import INoPublishLink
from nti.publishing.interfaces import ICalendarPublishable

from nti.recorder.interfaces import IRecordable
from nti.recorder.interfaces import IRecordableContainer

from nti.schema.field import Bool
from nti.schema.field import Dict
from nti.schema.field import Text
from nti.schema.field import Choice
from nti.schema.field import Object
from nti.schema.field import Number
from nti.schema.field import Iterable
from nti.schema.field import Timedelta
from nti.schema.field import ValidText
from nti.schema.field import ListOrTuple
from nti.schema.field import ValidDatetime
from nti.schema.field import ValidTextLine
from nti.schema.field import UniqueIterable
from nti.schema.field import TupleFromObject

from nti.schema.jsonschema import TAG_UI_TYPE
from nti.schema.jsonschema import UI_TYPE_EMAIL
from nti.schema.jsonschema import TAG_HIDDEN_IN_UI
from nti.schema.jsonschema import TAG_REQUIRED_IN_UI

#: The catalog entry NTIID provider
NTIID_ENTRY_PROVIDER = u'NTI'

#: The catalog entry NTIID type
NTIID_ENTRY_TYPE = u'CourseInfo'

#: NTIID Type for outline
NTI_COURSE_OUTLINE = u'NTICourseOutline'

#: NTIID Type for outline node
NTI_COURSE_OUTLINE_NODE = u'NTICourseOutlineNode'

# Permissions defined for courses here should also be
# registered in ZCML:
# from zope.security.permission import Permission
# ACT_XXX = Permission('nti.actions.XXX')

# Roles defined and used by this package

#: The ID of a role for instructors
RID_INSTRUCTOR = u"nti.roles.course_instructor"

#: The ID of a role for teaching assistants
RID_TA = u"nti.roles.course_ta"

#: The ID of the content editor role.
RID_CONTENT_EDITOR = u"nti.roles.course_content_editor"

#: Sections folder
SECTIONS = u'Sections'

#: Discussions folder
DISCUSSIONS = u'Discussions'

#: Courses folder
COURSE_CATALOG_NAME = u'Courses'

#: Course outline file name
COURSE_OUTLINE_NAME = u'course_outline.xml'

#: Instructor role
INSTRUCTOR = u"Instructor"

#: Editor role
EDITOR = u"Editor"

#: Outline node move type
TRX_OUTLINE_NODE_MOVE_TYPE = u'outlinenodemove'

#: Supported string keys
SUPPORTED_STRING_KEYS = (u'title',)

#: Supported bool keys
SUPPORTED_BOOL_KEYS = (u'excluded',)

#: Supported positive integer keys
SUPPORTED_PVE_INT_KEYS = (u'maximum_time_allowed', u'max_submissions')

#: Supported float keys
SUPPORTED_PVE_FLOAT_KEYS = (u'completion_passing_percent',)

#: Supported date keys
SUPPORTED_DATE_KEYS = (u'available_for_submission_beginning',
                       u'available_for_submission_ending')

#: NTI Course file scheme
NTI_COURSE_FILE = u'nti-course-file'
NTI_COURSE_FILE_SCHEME = u"%s:" % NTI_COURSE_FILE

# Notes:
#
# How to determine available courses?
#  -- Could either enumerate, or we maintain
#      a zope.catalog.Catalog (probably a catalog long term)
#
# How to tell what a user is enrolled in?
#  -- We could also use a zope.catalog.Catalog here,
#      but enrollment status effects permissioning,
#      not just of UGD (which previously was handled
#      implicitly through sharing things with a specific
#      DFL) but also of content. That means that
#      ACLs and "effective principals" get involved.
#      This could still be done with a DFL 'owned' by the
#      CourseInstance object, but a hierarchy can be extremely
#      useful (e.g., all students, ou students, ou grad students).
#      A hierarchy is offered by IPrincipal/IGroup and the
#      use of zope.pluggableauth.plugins.groupfolder,
#      so that's probably what we'll go with.
#
#      The remaining question is where the groupfolders live. pluggableauth
#      uses IAuthentication utilities, which are usually persistent
#      and which become active through traversal. If the groupfolder
#      is local to each ICourseInstance's SiteManager, this is handy
#      for permissioning and local editing, but not for global
#      queries. I really like the idea of local groupfolders,
#      so we may punt on that for now and do some sort of a
#      (cached) global enumeration when necessary until we
#      either do a catalog or manually keep a second datastructure.


class ICourseAdministrativeLevel(IFolder):
    """
    A container representing a level at which
    courses are administered. Specific instances
    or specific sub-interfaces may represent
    things like an organization or a department.

    Typically this will contain either other policy
    containers or instances of courses.
    """

    contains('.ICourseInstance',
             '.ICourseAdministrativeLevel')

    __setitem__.__doc__ = None


# Outlines


class _ICourseOutlineNodeContainer(interface.Interface):
    """
    Internal container for outline nodes.
    """


def _tag_iface_fields(iface, *fields):
    for name in fields:
        iface[name].setTaggedValue(TAG_HIDDEN_IN_UI, False)
        iface[name].setTaggedValue(TAG_REQUIRED_IN_UI, False)


class ICourseOutlineNode(IRecordableContainer,
                         IAttributeAnnotatable,
                         ITitledDescribedContent,
                         IOrderedContainer,
                         IContainerNamesContainer,
                         ICalendarPublishable,
                         IShouldHaveTraversablePath,
                         _ICourseOutlineNodeContainer):
    """
    A part of the course outline. Children are the sub-nodes of this
    entity, and are (typically) named numerically.

    .. note:: This is only partially modeled.
    """

    containers('._ICourseOutlineNodeContainer')
    contains('.ICourseOutlineNode')

    __parent__.required = False
    __setitem__.__doc__ = None

    src = ValidTextLine(title=u"json file to populate the node overview",
                        required=False)

    title = PlainTextLine(max_length=300,
                          required=False,
                          title=u"The human-readable title of this object",
                          __name__=u'title')

    LessonOverviewNTIID = ValidNTIID(title=u"The NTIID of the lesson overview",
                                     required=False,
                                     default=None)

    def append(node):
        """
        A synonym for __setitem__ that automatically handles naming.
        """

_tag_iface_fields(ICourseOutlineNode, 'title', 'description')


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
        title=u"This display time when this node should be active",
        description=u"""When present, this specifies the time instant at which
        this node and its children are to be available or active. If this is absent,
        it is always available or active. While this is represented here as an actual
        concrete timestamp, it is expected that in many cases the source representation
        will be relative to something else (a ``timedelta``) and conversion to absolute
        timestamp will be done as needed.""",
        required=False)

    AvailableEnding = ValidDatetime(
        title=u"This display time when this node should no longer be active",
        description=u"""When present, this specifies the last instance at which
        this node is expected to be available and active.
        As with ``available_for_submission_beginning``,
        this will typically be relative and converted.""",
        required=False)


_tag_iface_fields(ICourseOutlineCalendarNode,
                  'title', 'description', 'AvailableEnding', 'AvailableBeginning')


class ICourseOutlineContentNode(ICourseOutlineCalendarNode):
    """
    A part of a course outline that refers to
    a content unit.
    """

    ContentNTIID = ValidNTIID(title=u"The NTIID of the content this node uses",
                              required=False)


_tag_iface_fields(ICourseOutlineContentNode,
                  'title', 'description', 'AvailableEnding', 'AvailableBeginning')


class ICourseOutlineNodes(ISequence):
    """
    A marker interface for a sequence of outline nodes
    """


class ICourseOutline(ICourseOutlineNode,
                     ILastModified,
                     INoPublishLink):
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
    containers('.ICourseInstance')

    __parent__.required = False


class ICourseOutlineNodeMovedEvent(IObjectEvent):
    pass


@interface.implementer(ICourseOutlineNodeMovedEvent)
class CourseOutlineNodeMovedEvent(ObjectEvent):

    node = alias('object')

    def __init__(self, obj, principal=None, index=None, old_parent_ntiid=None):
        super(CourseOutlineNodeMovedEvent, self).__init__(obj)
        self.index = index
        self.principal = principal
        self.old_parent_ntiid = old_parent_ntiid


# Sharing

# Despite the notes at the top of this file about group-folders,
# we still stick to a fairly basic Community-derived
# object for sharing purposes. This is largely for compatibility
# and will change.


class ICourseInstanceSharingScope(ICommunity,
                                  IDisallowMembershipOperations,
                                  IUseNTIIDAsExternalUsername):
    """
    A sharing scope within an instance.
    """

    containers('.ICourseInstanceSharingScopes')

    __parent__.required = False


class ICourseInstanceSharingScopes(IContainer):
    """
    A container of sharing scopes for the course.

    See the documentation for :class:`ICourseInstanceEnrollmentRecord`
    for the expected keys in this scope.
    """

    contains(ICourseInstanceSharingScope)
    containers('.ICourseInstance')

    __parent__.required = False
    __setitem__.__doc__ = None

    def getAllScopesImpliedbyScope(scope_name):
        """
        Return all the :class:`ICourseInstanceSharingScope` objects
        implied by the given scope name, including the scope itself,
        creating them if necessary.
        """

# Discussions


from nti.dataserver.contenttypes.forums.interfaces import ICommunityBoard
from nti.dataserver.contenttypes.forums.interfaces import ICommunityForum
from nti.dataserver.contenttypes.forums.interfaces import IUseOIDForNTIID


class ICourseInstanceBoard(IUseOIDForNTIID, ICommunityBoard, IDefaultForumBoard):
    """
    Specialization of boards for courses.

    Note that courses are not required to contain
    this type of board in their Discussions property
    (for BWC, mostly), but this is required to be
    contained by a course.
    """
    containers('.ICourseInstance')


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

    SharingScopeName = interface.Attribute(
        "an optional field that should match the name of a sharing scope;"
        "If not found also check the tagged value on this attribute")


# Course instances


class ICourseSubInstances(IContainer):
    """
    A container for the subinstances (sections) of a course.
    """

    contains('.ICourseSubInstance')
    containers('.ICourseInstance')

    __parent__.required = False
    __setitem__.__doc__ = None


class ISynchronizable(interface.Interface):
    lastSynchronized = Number(title=u"The timestamp at which this object was last synchronized .",
                              default=0.0)
    lastSynchronized.setTaggedValue('_ext_excluded_out', True)



class IDoNotCreateDefaultOutlineCourseInstance(interface.Interface):
    """
    A marker interface for designating a course as not viable for
    creating a default outline.
    """

IDoNotCreateDefaultOutlineCourseInstance.setTaggedValue('_ext_is_marker_interface',
                                                        True)


class ICourseInstance(IFolder,
                      IShouldHaveTraversablePath,
                      _ICourseOutlineNodeContainer,
                      ISynchronizable,
                      IReportContext,
                      ICompletionContext):
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
                           title=u"The sharing scopes for this instance",
                           description=u"Each course has one or more sharing scopes. "
                           u"See :class:`ICourseInstanceEnrollmentRecord` for details.")
    # SharingScopes are externalized via a decorator to take into account
    # membership
    SharingScopes.setTaggedValue('_ext_excluded_out', True)

    Discussions = Object(IBoard,
                         title=u"The root discussion board for this course.",
                         description=u"Typically, courses will 'contain' their own discussions, "
                         u"but this may be a reference to another object.")

    Outline = Object(ICourseOutline,
                     title=u"The course outline or syllabus, if there is one.",
                     required=False)

    SubInstances = Object(ICourseSubInstances,
                          title=u"The sub-instances of this course, if any")
    SubInstances.setTaggedValue('_ext_excluded_out', True)

    # Reflecting instructors, TAs, and other affiliated
    # people with a special role in the course:
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

    # JAM: 20140716: The above description has now been surpassed,
    # and we are in fact using a structured role model. The use of
    # this attribute is deprecated. It in fact holds everyone, both
    # instructors and TAs and others.
    instructors = UniqueIterable(title=u"The principals that are the instructors of the course.",
                                 description=u"They get special access rights.",
                                 value_type=Object(IPrincipal))
    instructors.setTaggedValue('_ext_excluded_out', True)


class INonExportable(interface.Interface):
    """
    Marker interface for those :class:`ICourseInstance` objects which may not
    be exportable.
    """


class ICourseSubInstance(ICourseInstance, INonExportable):
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
                                  title=u"The content package associated with this course.")

    root = Object(IEnumerableDelimitedHierarchyBucket,
                  title=u"The on-disk bucket containing descriptions for this object",
                  default=None,
                  required=False)
    root.setTaggedValue('_ext_excluded_out', True)


class IContentCourseSubInstance(ICourseSubInstance, IContentCourseInstance):
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
IEnrollmentMappedCourseInstance.setTaggedValue('_ext_is_marker_interface',
                                               True)


class ICourseInstanceVendorInfo(IEnumerableMapping,
                                IExtendedWriteMapping,
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
# both spellings are acceptable
ICourseInstanceVenderInfo = ICourseInstanceVendorInfo


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


class IAnonymouslyAccessibleCourseInstance(interface.Interface):
    """
    A marker interface applied to course instances to designate
    that they are accessible via anonymous requests (unauthenticated)
    users.  Although this marks anonymously accessible courses these
    courses are not "publicly" accessible.  Authenticated users cannot
    access them without being enrolled.
    """
# Don't try to consider this when determining most-derived
# interfaces.
IAnonymouslyAccessibleCourseInstance.setTaggedValue('_ext_is_marker_interface', True)


class IDenyOpenEnrollment(interface.Interface):
    """
    A marker interface applied to course instances to designate
    that they don't allow open enrollment
    people enrolled for credit can see the catalog entry and the
    course itself. This enrollment typically happens in a backend
    process.
    """
# Don't try to consider this when determining most-derived
# interfaces.
IDenyOpenEnrollment.setTaggedValue('_ext_is_marker_interface', True)


# Catalog


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

    def getAdminLevels():
        """
        Returns a mapping of admin key to :class:`.ICourseAdministrativeLevel`.

        Entries from this site level shadow entries from
        higher site levels, and entries from this site
        level are returned first.
        """


from persistent.interfaces import IPersistent


class IPersistentCourseCatalog(ICourseCatalog, IPersistent, IContainer):
    """
    A locally persistent course catalog; contrast with the global
    course catalog.
    """


class IWritableCourseCatalog(ICourseCatalog, IContentContainer):
    """
    A type of course catalog that is expected to behave like
    a container and be writable.
    """

    contains('.ICourseCatalogEntry')

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


def checkEmailAddress(value):
    if value and isValidMailAddress(value):
        return True
    ex = InvalidData(value)
    ex.i18n_message = _(u"The email address you have entered is not valid.")
    raise ex


class ICourseCatalogInstructorInfo(interface.Interface):
    """
    Information about a course instructor.

    .. note:: Almost all of this could/should
            come from a user profile. That way the user
            can be in charge of it. Pictures would come from
            the user's avatar URL.
    """

    Name = ValidTextLine(title=u"The instructor's name")

    Title = ValidTextLine(title=u"The instructor's title of address such as Dr.",
                          required=False)

    JobTitle = ValidTextLine(title=u"The instructor's academic job title",
                             required=False)

    Suffix = ValidTextLine(title=u"The instructor's suffix such as PhD or Jr",
                           required=False)

    Email = ValidTextLine(title=u"The instructor's email",
                          required=False,
                          constraint=checkEmailAddress)
    Email.setTaggedValue(TAG_REQUIRED_IN_UI, True)
    Email.setTaggedValue(TAG_UI_TYPE, UI_TYPE_EMAIL)

    Biography = HTMLContentFragment(title=u"The instructor's biography",
                                    required=False,
                                    default=u'')


class ICatalogFamily(IDisplayableContent):

    ProviderUniqueID = ValidTextLine(title=u"The unique id assigned by the provider",
                                     required=True,
                                     max_length=32,
                                     min_length=1)

    ProviderDepartmentTitle = ValidTextLine(title=u"The string assigned to the provider's department offering the course",
                                            required=False)

    StartDate = ValidDatetime(title=u"The date on which the course begins",
                              description=u"Currently optional; a missing value means the course already started",
                              required=False)

    EndDate = ValidDatetime(title=u"The date on which the course ends",
                            description=u"Currently optional; a missing value means the course has no defined end date.",
                            required=False)

    # don't required dublin core IDCDescriptiveProperties
    title = ValidTextLine(title=u"The human-readable section name of this item",
                          required=True,
                          min_length=1,
                          max_length=140)

    description = ValidText(title=u"The human-readable description",
                            default=u'',
                            required=False)

    # don't required dublin core IDCExtended
    creators = ListOrTuple(title=u'Creators',
                           description=u"The unqualified Dublin Core 'Creator' element values",
                           value_type=ValidTextLine(),
                           default=(),
                           required=False)
    creators.setTaggedValue('_ext_excluded_out', True)

    subjects = ListOrTuple(title=u'Subjects',
                           description=u"The unqualified Dublin Core 'Subject' element values",
                           value_type=ValidTextLine(),
                           required=False)
    subjects.setTaggedValue('_ext_excluded_out', True)

    publisher = Text(title=u'Publisher',
                     description=u"The first unqualified Dublin Core 'Publisher' element value.",
                     required=False)
    publisher.setTaggedValue('_ext_excluded_out', True)

    contributors = ListOrTuple(title=u'Contributors',
                               description=u"The unqualified Dublin Core 'Contributor' element values",
                               value_type=ValidTextLine(),
                               required=False)
    contributors.setTaggedValue('_ext_excluded_out', True)


class MultiWordTag(PlainTextLine):
    """
    Tags that may span multiple, lowercase words.
    """

    def fromUnicode(self, value):  # pylint: disable=arguments-differ
        return super(MultiWordTag, self).fromUnicode(value.lower())


class ICourseCatalogEntry(ICatalogFamily,
                          ILastModified,
                          IShouldHaveTraversablePath,
                          IContained,
                          ISynchronizable,
                          IRecordable,
                          IAwardableCreditContext):
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

    containers(ICourseCatalog, ICourseInstance)

    __parent__.required = False

    # Used to have Title/Description, now the lower case versions.
    # The T/D should be aliased in implementations.

    Instructors = ListOrTuple(title=u"The instructors. Order might matter",
                              value_type=Object(ICourseCatalogInstructorInfo),
                              required=False,
                              default=())

    InstructorsSignature = ValidText(title=u"The sign-off or closing signature of the instructors",
                                     description=u"As used in an email. If this is not specifically provided, "
                                     u"one can be derived from the names and titles of the instructors.",
                                     required=False,
                                     default=u'')
    InstructorsSignature.setTaggedValue('_ext_excluded_out', True)

    Duration = Timedelta(title=u"The length of the course",
                         description=u"Currently optional, may be None",
                         required=False)

    AdditionalProperties = Dict(title=u"dictionary of additional unmodeled data",
                                required=False)

    RichDescription = HTMLContentFragment(title=u"An embelished version of the description of this course",
                                          description=u"""An HTMLContentFragment providing an embelished description
                                          for the course.  This provides storage for a description with basic html formatting""",
                                          required=False,
                                          default=u'')

    tags = TupleFromObject(title=u"Applied Tags",
                           value_type=MultiWordTag(min_length=1,
                                                   max_length=64,
                                                   title=u"A single tag",
                                                   __name__=u'tags'),
                           unique=True,
                           default=())

    AvailableToEntityNTIIDs = ListOrTuple(title=u"Available to entity ntiids",
                                          description=u"""Entities who have access (e.g. enrollment) to this entry.""",
                                          value_type=ValidTextLine(title=u'The entity ntiid'),
                                          required=False,
                                          default=())

    def isCourseCurrentlyActive():
        """
        Return a boolean value answering whether the course
        should be considered active, taking into account any information
        about starting and ending dates and durations, preview
        flags, etc.
        """


# Enrollments


#: Open enrollment
OPEN = u'Open'

#: Purchased enrollment
PURCHASED = u'Purchased'

#: For Credit enrollment
FOR_CREDIT = u'For Credit'

#: For Credit Degree Enrollment
FOR_CREDIT_DEGREE = u'For Credit (Degree)'

#: For Credit Non Degree Enrollment
FOR_CREDIT_NON_DEGREE = u'For Credit (Non-degree)'

#: Vendor key Credit Enrollment
IN_CLASS = u'In-Class'

#: Vendor key prefix Credit Enrollment
IN_CLASS_PREFIX = u'InClass'

#: Scope
SCOPE = u'Scope'

#: Scope Description
DESCRIPTION = u'Description'

#: Now we list the scopes and create a vocabulary
#: for them. In the future, we can use a vocabularyregistry
#: to have these be site-specific.
ES_ALL = u'All'

#: The "root" enrollment or sharing scope; everyone enrolled or administrating
#: is a member of this scope.
#: sharing scopes are conceptually arranged in a strict hierarchy, and
#: every enrollment record is within one specific scope. Because
#: scope objects do not actually nest (are non-transitive), it is implied that
#: a member of a nested scope will actually also be members of
#: the parent scopes.
ES_PUBLIC = u"Public"

#: This scope extends the public scope with people that have purchase the course
ES_PURCHASED = u"Purchased"

#: This scope extends the public scope with people taking the course
#: to earn academic credit. They have probably paid money.
ES_CREDIT = u"ForCredit"

#: This scope extends the ForCredit scope to be specific to people who
#: are engaged in a degree-seeking program.
ES_CREDIT_DEGREE = u"ForCreditDegree"

#: This scope extends the ForCredit scope to be specific to people who
#: are taking the course for credit, but are not engaged in
#: seeking a degree.
ES_CREDIT_NONDEGREE = u"ForCreditNonDegree"

from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


class ScopeTerm(SimpleTerm):

    def __init__(self, value, title=None, implies=(), implied_by=(),
                 vendor_key=None, vendor_key_prefix=None):
        SimpleTerm.__init__(self, value, title=title)
        self.implies = implies
        self.implied_by = implied_by
        self.vendor_key = vendor_key if vendor_key else value
        self.vendor_key_prefix = vendor_key_prefix if vendor_key_prefix else value


ENROLLMENT_SCOPE_VOCABULARY = SimpleVocabulary(
    [ScopeTerm(ES_PUBLIC,
               title=_(OPEN),
               implied_by=(ES_CREDIT, ES_CREDIT_DEGREE,
                           ES_CREDIT_NONDEGREE, ES_PURCHASED),
               vendor_key=OPEN,
               vendor_key_prefix=OPEN),
     ScopeTerm(ES_PURCHASED,
               title=_(PURCHASED),
               implies=(ES_PUBLIC,),
               implied_by=(ES_CREDIT, ES_CREDIT_DEGREE, ES_CREDIT_NONDEGREE)),
     ScopeTerm(ES_CREDIT,
               title=_(FOR_CREDIT),
               implies=(ES_PUBLIC, ES_PURCHASED),
               implied_by=(ES_CREDIT_DEGREE, ES_CREDIT_NONDEGREE),
               vendor_key=IN_CLASS,
               vendor_key_prefix=IN_CLASS_PREFIX),
     ScopeTerm(ES_CREDIT_DEGREE,
               title=_(FOR_CREDIT_DEGREE),
               implies=(ES_CREDIT, ES_PURCHASED, ES_PUBLIC),
               implied_by=()),
     ScopeTerm(ES_CREDIT_NONDEGREE,
               title=_(FOR_CREDIT_NON_DEGREE),
               implies=(ES_CREDIT, ES_PURCHASED, ES_PUBLIC),
               implied_by=())])

ENROLLMENT_SCOPE_MAP = {x.value: x for x in ENROLLMENT_SCOPE_VOCABULARY}
ENROLLMENT_SCOPE_NAMES = tuple(ENROLLMENT_SCOPE_MAP.keys())

ENROLLMENT_LINEAGE_MAP = {
    ES_ALL: (ES_PUBLIC, ES_CREDIT),
    ES_PUBLIC: (ES_PUBLIC,),
    ES_CREDIT: (ES_CREDIT,),
    ES_PURCHASED: (ES_CREDIT,),
    ES_CREDIT_DEGREE: (ES_CREDIT,),
    ES_CREDIT_NONDEGREE: (ES_CREDIT,)
}


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
                            title=u"The course instance",
                            description=u"This should also be in the lineage of this object. "
                            u"This is to allow ObjectMovedEvents to be able to find both the current "
                            u"and previous course, given the current and previous parents",
                            required=False)

    Principal = Object(interface.Interface,
                       title=u"The principal this record is for",
                       required=False)

    Scope = Choice(title=u"The name of the enrollment scope",
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

    def count_enrollments():
        """
        Count enrollments for the context.
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

    def is_principal_enrolled(principal):
        """
        Given the same kind of principal that was enrolled
        with the course enrollment manager, return
        true of the principal is enrolled; false otherwise
        """

    def get_enrollment_for_principal(principal):
        """
        Given the same kind of principal that was enrolled
        with the course enrollment manager, return
        the enrollment record for that principal.

        If the principal is not enrolled, return None.
        """


class IDefaultCourseInstanceEnrollmentStorage(ICourseInstanceEnrollmentRecordContainer,
                                              IContained):
    """
    Maps from principal ids to their enrollment record.
    """
    contains(ICourseInstanceEnrollmentRecord)


class IDefaultCourseCatalogEnrollmentStorage(IContainer, IContained):
    """
    Maps from principal IDs to a persistent list of their
    enrollments. Intended to be installed on the course catalog that
    contains the courses referenced.
    """

    def enrollments_for_id(principalid, principal):
        """
        Return the mutable list/set-like object to hold record references
        for the principal.

        :param principal: If this has a non-None `_p_jar`, the enrollment
                list will be stored in this jar.
        """


class IEnrollmentException(IGrantAccessException):
    """
    marker interface for enrollment exception"
    """


@interface.implementer(IEnrollmentException)
class AlreadyEnrolledException(ValidationError):
    __doc__ = _(u'User already enrolled in course.')
    i18n_message = __doc__


@interface.implementer(IEnrollmentException)
class InstructorEnrolledException(ValidationError):
    __doc__ = _(u'Instructor cannot enroll in course.')
    i18n_message = __doc__


class CourseAlreadyExistsException(ValidationError):
    __doc__ = _(u"Course already exists.")
    i18n_message = __doc__


class OpenEnrollmentNotAllowedException(ValidationError):
    __doc__ = _(u"Open Enrollment is not allowed.")
    i18n_message = __doc__


class ICourseInstanceAvailableEvent(IObjectEvent):
    """
    An event that is sent, usually during startup or synchronization,
    to notify that a course instance has been setup by this package.
    This is a hook for additional packages to perform any setup they
    need to do, such as synchronizing database state with course
    content state.
    """

    bucket = Object(IDelimitedHierarchyBucket, title=u"Bucket", required=False)

    results = Object(ISynchronizationResults,
                     title=u"Sync Results", required=False)


@interface.implementer(ICourseInstanceAvailableEvent)
class CourseInstanceAvailableEvent(ObjectEvent):

    def __init__(self, obj, bucket=None, results=None):
        super(CourseInstanceAvailableEvent, self).__init__(obj)
        self.bucket = bucket
        self.results = results


class ICourseContentPackageBundle(IEditableContentPackageBundle):
    pass


class ICourseBundleUpdatedEvent(IObjectEvent):
    """
    An event that is sent, usually during startup or synchronization,
    to notify that a course instance bundle has been updated, typically
    by adding or removing :class:`IContentPackage` objects.
    """


class AbstractCourseBundleUpdateEvent(ObjectEvent):

    course = alias('object')

    def __init__(self, obj, added_packages=(), removed_packages=()):
        super(AbstractCourseBundleUpdateEvent, self).__init__(obj)
        self.added_packages = added_packages
        self.removed_packages = removed_packages


@interface.implementer(ICourseBundleUpdatedEvent)
class CourseBundleUpdatedEvent(AbstractCourseBundleUpdateEvent):
    pass


class ICourseBundleWillUpdateEvent(IObjectEvent):
    """
    An event that is sent, usually during startup or synchronization,
    to notify that a course instance bundle will be updated, typically
    by adding or removing :class:`IContentPackage` objects.
    """


@interface.implementer(ICourseBundleWillUpdateEvent)
class CourseBundleWillUpdateEvent(AbstractCourseBundleUpdateEvent):
    pass


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


# Back to discussions


class ICourseInstancePublicScopedForum(ICourseInstanceScopedForum):

    SharingScopeName = ValidTextLine(description=u"Should be the same as ES_PUBLIC",
                                     required=False,
                                     default=ES_PUBLIC)
    SharingScopeName.setTaggedValue('value', ES_PUBLIC)


class ICourseInstanceForCreditScopedForum(ICourseInstanceScopedForum):
    """
    A forum intended to be visible to those enrolled for credit.
    """

    SharingScopeName = ValidTextLine(description=u"Should be the same as ES_CREDIT",
                                     required=False,
                                     default=ES_CREDIT)
    SharingScopeName.setTaggedValue('value', ES_CREDIT)


class ICourseInstancePurchasedScopedForum(ICourseInstanceScopedForum):
    """
    A forum intended to be visible to those who have purchased a course.
    """

    SharingScopeName = ValidTextLine(description=u"Should be the same as ES_PURCHASED",
                                     required=False,
                                     default=ES_PURCHASED)
    SharingScopeName.setTaggedValue('value', ES_PURCHASED)


# Synchronizer


class ICourseLessonSyncResults(IGenericSynchronizationResults):

    LessonsUpdated = ListOrTuple(title=u"Lessons updated on sync.",
                                 required=False)

    LessonsSyncLocked = ListOrTuple(title=u"Lessons not updated due to sync locks.",
                                    required=False)


@interface.implementer(ICourseLessonSyncResults)
class CourseLessonSyncResults(object):

    def __init__(self):
        self.LessonsUpdated = []
        self.LessonsSyncLocked = []


class ICourseSynchronizationResults(IGenericSynchronizationResults):

    NTIID = ValidTextLine(title=u"Course NTIID", required=False)

    CatalogEntryUpdated = Bool(title=u"CatalogEntry updated",
                               required=False,
                               default=False)

    SharingScopesUpdated = Bool(title=u"Sharing scopes updated",
                                required=False,
                                default=False)

    CourseDiscussionsUpdated = Bool(title=u"Sharing scopes updated",
                                    required=False,
                                    default=False)

    ContentBundleCreated = Bool(title=u"Bundle created",
                                required=False,
                                default=False)
    ContentBundleUpdated = Bool(title=u"Bundle updated",
                                required=False,
                                default=False)

    VendorInfoReseted = Bool(title=u"Vendor info reseted",
                             required=False, default=False)

    VendorInfoUpdated = Bool(title=u"Vendor info updated",
                             required=False, default=False)

    OutlineDeleted = Bool(title=u"Outline deleted",
                          required=False, default=False)

    OutlineUpdated = Bool(title=u"Outline updated",
                          required=False,
                          default=False)

    InstructorRolesReseted = Bool(title=u"Instructor Roles reseted",
                                  required=False,
                                  default=False)

    InstructorRolesUpdated = Bool(title=u"Instructor Roles updated",
                                  required=False,
                                  default=False)

    AssignmentPoliciesReseted = Bool(title=u"Assignment Policies reseted",
                                     required=False,
                                     default=False)
    AssignmentPoliciesUpdated = Bool(title=u"Assignment Policies updated",
                                     required=False,
                                     default=False)

    GradingPolicyUpdated = Bool(title=u"Grading Policy updated",
                                required=False,
                                default=False)

    EvaluationsUpdated = Bool(title=u"Course Evaluations",
                              required=False,
                              default=False)

    Lessons = Object(ICourseLessonSyncResults,
                     title=u"Lesson Results", required=False)

    Site = ValidTextLine(title=u"Site Name", required=False)


class IObjectEntrySynchronizer(interface.Interface):
    """
    Something to synchronize one object and possibly its children.
    """

    def synchronize(obj, bucket, **kwargs):
        """
        Synchronize the object from the bucket.
        """


class ICatalogEntrySynchronized(IObjectEvent):
    pass


@interface.implementer(ICatalogEntrySynchronized)
class CatalogEntrySynchronized(ObjectEvent):
    pass


class ICourseRolesSynchronized(IObjectEvent):
    pass


@interface.implementer(ICourseRolesSynchronized)
class CourseRolesSynchronized(ObjectEvent):
    pass


class ICourseRoleUpdatedEvent(IObjectEvent):
    """
    Event to indicate a course role has been updated.
    """


class AbstractCourseRoleUpdatedEvent(ObjectEvent):

    user = alias('object')

    def __init__(self, obj, course):
        super(AbstractCourseRoleUpdatedEvent, self).__init__(obj)
        self.course = course


class ICourseRoleAddedEvent(ICourseRoleUpdatedEvent):
    """
    Event to indicate a user has been added to a course role.
    """


class ICourseInstructorAddedEvent(ICourseRoleAddedEvent):
    """
    Event to indicate a user has been added as a course instructor.
    """


@interface.implementer(ICourseInstructorAddedEvent)
class CourseInstructorAddedEvent(AbstractCourseRoleUpdatedEvent):
    pass


class ICourseEditorAddedEvent(ICourseRoleAddedEvent):
    """
    Event to indicate a user has been added as a course editor.
    """


@interface.implementer(ICourseEditorAddedEvent)
class CourseEditorAddedEvent(AbstractCourseRoleUpdatedEvent):
    pass


class ICourseRoleRemovedEvent(ICourseRoleUpdatedEvent):
    """
    Event to indicate a user has been removed from a course role.
    """


class ICourseInstructorRemovedEvent(ICourseRoleRemovedEvent):
    """
    Event to indicate a user has been removed as a course instructor.
    """


@interface.implementer(ICourseInstructorRemovedEvent)
class CourseInstructorRemovedEvent(AbstractCourseRoleUpdatedEvent):
    pass


class ICourseEditorRemovedEvent(ICourseRoleRemovedEvent):
    """
    Event to indicate a user has been removed as a course editor.
    """


@interface.implementer(ICourseEditorRemovedEvent)
class CourseEditorRemovedEvent(AbstractCourseRoleUpdatedEvent):
    pass


class ICourseVendorInfoSynchronized(IObjectEvent):
    pass


@interface.implementer(ICourseVendorInfoSynchronized)
class CourseVendorInfoSynchronized(ObjectEvent):
    pass


class ICourseCatalogDidSyncEvent(IObjectEvent):
    """
    A course catalog completed synchronization, with or without changes.
    """

    params = Object(ISynchronizationParams,
                    title=u"Synchronization parameters",
                    required=False)

    results = Object(ISynchronizationResults,
                     title=u"Synchronization results",
                     required=False)


@interface.implementer(ICourseCatalogDidSyncEvent)
class CourseCatalogDidSyncEvent(ObjectEvent):

    def __init__(self, obj, params=None, results=None):
        super(CourseCatalogDidSyncEvent, self).__init__(obj)
        self.params = params
        self.results = results

# assesments


class ICourseAssessmentItemCatalog(interface.Interface):
    """
    Provides access to the assessment items (questions, question sets,
    assignments) related to a course.

    Typically this will be registered as an adapter
    from the :class:`.ICourseInstance`.
    """

    def iter_assessment_items():
        """
        Return the items.

        Recall that items typically will have their 'home'
        content unit in their lineage.
        """


class ICourseSelfAssessmentItemCatalog(ICourseAssessmentItemCatalog):
    """
    Provides access to the assessment items (questions, question sets,
    assignments) related to a course.

    Typically this will be registered as an adapter
    from the :class:`.ICourseInstance`.
    """

    def iter_assessment_items(exclude_editable=True):
        pass


class ICourseAssignmentCatalog(interface.Interface):
    """
    Provides access to the assignments related to a course.

    Typically this will be registered as an adapter
    from the :class:`.ICourseInstance`.
    """

    def iter_assignments(course_lineage=False):
        """
        Return the assignments.

        Recall that assignments typically will have their 'home'
        content unit in their lineage.

        if `course_lineage`, we also include the assignments defined
        in the parent course (if available).
        """


class ICourseAssessmentUserFilter(interface.Interface):
    """
    A filter to determine if a user should be able to see
    an assessment.

    These will typically be registered as subscription adapters
    from the user and the course.
    """

    def allow_assessment_for_user_in_course(assignment, user, course):
        """
        Given a user and an :class:`.ICourseInstance` the user is enrolled in, return a
        callable that takes an assessment and returns True if the
        assignment should be visible to the user and False otherwise.
        """


class ICourseInstanceAdministrativeRole(IShouldHaveTraversablePath):
    """
    An object representing a principal's administrative
    role within a course instance.

    Currently, the only supported role is that of instructor, and that
    role is static; thus, this object cannot be deleted or altered
    externally.) In the future as there are more roles (such as TA)
    and those roles are made dynamic, instances of this
    object may be able to be DELETEd or POSTd.

    Implementations should be adaptable to their course instance
    and the corresponding catalog entry.
    """

    __name__ = interface.Attribute("The name of the administration is the same as the CourseInstance.")

    RoleName = Choice(title=u"The name of the role this principal holds",
                      values=('instructor', 'teaching assistant', 'editor'))
    CourseInstance = Object(ICourseInstance)
    CourseInstance.setTaggedValue('_ext_excluded_out', True)


class IPrincipalAdministrativeRoleCatalog(interface.Interface):
    """
    Something that can provide information about all courses
    administered by the principal.

    There can be multiple catalogs for courses that are managed in
    different ways. Therefore, commonly implementations will be
    registered as subscription adapters from the user.
    """

    def iter_administrations():
        """
        Iterate across :class:`.ICourseInstanceAdministrativeRole` objects, or at
        least something that can be adapted to that interface.
        """

    def count_administrations():
        """
        return the count of administrator roles
        """


class ICourseRolePermissionManager(IRolePermissionManager):
    """
    A role permission manager for courses.
    """

    def initialize():
        """
        Initialize our role manager to default status.
        """


class IUserAdministeredCourses(interface.Interface):
    """
    Marker for a callable utility that return the administered courses of a user
    """

    def iter_admin(user):
        """
        return an iterable with the users administered courses
        """


def get_course_assessment_predicate_for_user(user, course):
    """
    Given a user and an :class:`.ICourseInstance` the user is enrolled in, return a
    callable that takes an assessment and returns True if the
    assignment should be visible to the user and False otherwise.

    Delegates to :class:`.ICourseAssessmentUserFilter` subscribers.

    .. note:: Those subscribers probably implicitly assume that
            the assessment passed to them is actually hosted within the
            course.
    """
    filters = component.subscribers((user, course),
                                    ICourseAssessmentUserFilter)
    filters = list(filters)

    def uber_filter(asg):
        return all((f.allow_assessment_for_user_in_course(asg, user, course) for f in filters))
    return uber_filter


class ICourseCatalogEntryFilterUtility(interface.Interface):
    """
    A utility to fetch filter :class:`ICourseCatalogEntry` objects.
    """

    def filter_entries(entries, filter_str):
        """
        Returns a filtered sequence of included :class:`ICourseCatalogEntry`
        matches the given filter str. `entry` may be a single instance
        or a sequence. The given order is maintained.
        """


# Invitations


class CourseInvitationException(ValidationError):
    pass


class CourseCatalogUnavailableException(CourseInvitationException):
    __doc__ = _(u"Course catalog not available.")
    i18n_message = __doc__


class CourseNotFoundException(CourseInvitationException):
    __doc__ = _(u"Course not found.")
    i18n_message = __doc__


class IJoinCourseInvitation(IUserInvitation):
    """
    Marker interface for a invitation to join a course
    """
    course = ValidTextLine(title=u"The NTIID of the course.", required=False)

    scope = ValidTextLine(title=u"The enrollment scope.", required=False)

    name = ValidTextLine(title=u"Invitation receiver name.", required=False)

    email = ValidTextLine(title=u"Invitation receiver email.", required=False)


class IJoinCourseInvitationActor(IInvitationActor):
    """
    Actor to enroll a user in a course
    """
    pass


# Import / Export


class ICreatedCourse(interface.Interface):
    """
    Course created by an identified entity.
    """
    creator = interface.Attribute(u"The creator of this object.")
ICreatedCourse.setTaggedValue('_ext_is_marker_interface', True)


class ICourseExportFiler(ISourceFiler):

    def prepare(**kwargs):
        """
        prepare filer for use
        """

    def reset():
        """
        remove all content from this filer
        """

    def asZip(path=None):
        """
        zip all contents of this filer in a zipe file

        :parm path export path
        :return a zile file name
        """


class ICourseExporter(interface.Interface):

    def export(course, filer, backup=True, salt=None):
        """
        Export the specified course

        :param course: Course to export
        :param filer: External filter to export objects
        :param backup: Backup flag
        :param salt: ntiid salt
        """


class ICourseSectionExporter(interface.Interface):
    """
    Export a course section
    """

    def export(course, filer, backup=True, salt=None):
        """
        Export the specified course

        :param course: Course to export
        :param filer: External source filer
        :param backup: backup flag
        :param salt: ntiid salt
        """


class ICourseImporter(interface.Interface):

    def process(course, filer, writeout=True):
        """
        Import the specified course

        :param course: Course to import
        :param filer: External source filer
        :param writeout: Boolean to save source files to disk
        """


class ICourseSectionImporter(interface.Interface):

    def process(course, filer, writeout=True):
        """
        Import the specified course

        :param course Course to import
        :param filer: External source filer
        :param writeout: Boolean to save source files to disk
        """


class ICourseEvaluationImporter(interface.Interface):

    def process_source(course, source, filer=None):
        """
        Import the specified course evaluations

        :param course Course to import
        :param source Source to process
        :param filer: External source filer
        """


class ICourseCompletionSectionExporter(ICourseSectionExporter):
    pass


class ICourseCompletionSectionImporter(ICourseSectionImporter):
    pass


class CourseImportException(ValidationError):
    """
    A generic course import exception.
    """


class DuplicateImportFromExportException(CourseImportException):
    """
    We prevent courses from being imported with the same export zip since we do
    not want ntiids to collide.
    """


class InvalidCourseArchiveException(ValidationError):
    """
    We prevent courses from being imported using invalid course archives.
    """


class ImportCourseTypeUnsupportedError(ValidationError):
    """
    Error raised when a course of an unsupported type is imported.
    """


class ICourseInstanceExportedEvent(IObjectEvent):
    pass


@interface.implementer(ICourseInstanceExportedEvent)
class CourseInstanceExportedEvent(ObjectEvent):
    pass


class ICourseInstanceImportedEvent(IObjectEvent):
    pass


@interface.implementer(ICourseInstanceImportedEvent)
class CourseInstanceImportedEvent(ObjectEvent):
    pass


class ICourseSectionExporterExecutedEvent(IObjectEvent):
    exporter = interface.Attribute("The exporter object.")
    filer = interface.Attribute("The filer object.")
    salt = interface.Attribute("The salt string.")
    backup = interface.Attribute("The backup flag.")


@interface.implementer(ICourseSectionExporterExecutedEvent)
class CourseSectionExporterExecutedEvent(ObjectEvent):

    def __init__(self, course, exporter, filer=None, backup=True, salt=None):
        ObjectEvent.__init__(self, course)
        self.salt = salt
        self.filer = filer
        self.backup = backup
        self.exporter = exporter


class ICourseSectionImporterExecutedEvent(IObjectEvent):
    importer = interface.Attribute("The importer object.")
    filer = interface.Attribute("The filer object.")
    writeout = interface.Attribute("The writeout flag.")


@interface.implementer(ICourseSectionImporterExecutedEvent)
class CourseSectionImporterExecutedEvent(ObjectEvent):

    def __init__(self, course, importer, filer=None, writeout=False):
        ObjectEvent.__init__(self, course)
        self.filer = filer
        self.importer = importer
        self.writeout = writeout


class ICourseImportMetadata(interface.Interface):
    """
    Contains import metadata information for this.
    """

    last_import_hash = interface.Attribute("The export hash value of the data used to import this course.")
    last_import_time = interface.Attribute("The last date time this course was imported onto.")


class ICourseTabPreferences(IContained):
    """
    Contains course tab/string information.
    """

    def update_names(names):
        pass

    def update_order(order):
        pass

    def clear():
        pass

    def __nonzero__():
        """
        implement truth value testing
        """
    __bool__ = __nonzero__

# removal


class ICourseInstanceRemovedEvent(IObjectEvent):
    """
    An event that is sent after a course has been removed
    """
    site = interface.Attribute("Course site")
    course = interface.Attribute("Course removed")
    entry = interface.Attribute("Course catalog entry")


@interface.implementer(ICourseInstanceRemovedEvent)
class CourseInstanceRemovedEvent(ObjectEvent):

    def __init__(self, obj, entry, site):
        super(CourseInstanceRemovedEvent, self).__init__(obj)
        self.site = site
        self.entry = entry

    @property
    def course(self):
        return self.object


# index


class ICourseKeywords(interface.Interface):
    keywords = Iterable(title=u"Course key words")


class ICourseAwardedCredit(IAwardedCredit):
    """
    :class:`IAwardedCredit` awarded for completing courses.
    """


class ICourseAwardableCredit(IAwardableCredit):
    """
    An :class:`IAwardableCredit` that include a scope, indicating which class of students
    the credit is applicable to.
    """

    scope = Choice(title=u"The name of the enrollment scope",
                   vocabulary=ENROLLMENT_SCOPE_VOCABULARY,
                   default=ES_PUBLIC,
                   required=False)


class ICourseContentLibraryProvider(interface.Interface):
    """
    An intended subscriber provider of course content mimetypes that can be added to
    lessons based on a user and course.
    """

    def get_item_mime_types():
        """
        Returns the collection of mimetypes that may be available (either
        they exist or can exist) in this course.
        """


#: All course outline node interfaces
ALL_COURSE_OUTLINE_INTERFACES = (ICourseOutlineContentNode,
                                 ICourseOutlineCalendarNode,
                                 ICourseOutlineNode)


def iface_of_outline_node(node):
    for node_interface in (ICourseOutlineContentNode,
                           ICourseOutlineCalendarNode,
                           ICourseOutlineNode,
                           ICourseOutline):  # order matters
        if node_interface.providedBy(node):
            return node_interface
    return None
iface_of_node = iface_of_outline_node  # alias


def _set_ifaces():
    for iSchema in ALL_COURSE_OUTLINE_INTERFACES:
        for k, v in iSchema.namesAndDescriptions(all=True):
            if IMethod.providedBy(v) or v.queryTaggedValue(TAG_HIDDEN_IN_UI) is not None:
                continue
            iSchema[k].setTaggedValue(TAG_HIDDEN_IN_UI, True)
_set_ifaces()
del _set_ifaces
del _tag_iface_fields

import zope.deferredimport
zope.deferredimport.initialize()
zope.deferredimport.deprecatedFrom(
    "Moved to nti.contenttypes.courses.grading.interfaces",
    "nti.contenttypes.courses.grading.interfaces",
    "ICourseGradingPolicy"
)

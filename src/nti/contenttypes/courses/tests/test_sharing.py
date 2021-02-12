#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import contains
from hamcrest import contains_inanyorder
from hamcrest import equal_to
from hamcrest import has_length
from hamcrest import has_property
from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import raises
from hamcrest import same_instance
from hamcrest import starts_with

from nti.dataserver.tests.mock_dataserver import DataserverLayerTest
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.testing.matchers import is_empty
from nti.testing.matchers import validly_provides

import fudge
import unittest

from nti.contenttypes.courses import sharing
from nti.contenttypes.courses import interfaces

from ZODB.interfaces import IConnection


class TestSharing(unittest.TestCase):

    def test_provides(self):
        assert_that(sharing.CourseInstanceSharingScope('foo'),
                    validly_provides(interfaces.ICourseInstanceSharingScope))

        assert_that(sharing.CourseInstanceSharingScopes(),
                    validly_provides(interfaces.ICourseInstanceSharingScopes))

    def test_get_scopes(self):
        scopes = sharing.CourseInstanceSharingScopes()

        all_scopes = scopes.getAllScopesImpliedbyScope('ForCreditNonDegree')
        all_scopes = list(all_scopes)

        assert_that(all_scopes,
                    contains_inanyorder(
                        has_property('__name__', interfaces.ES_PUBLIC),
                        has_property('__name__', interfaces.ES_CREDIT),
                        has_property('__name__', interfaces.ES_PURCHASED),
                        has_property('__name__', interfaces.ES_CREDIT_NONDEGREE)
                    ))

    def test_scope_eq_hash(self):
        # Scopes are equal and hash based on their ntiid
        # which is an oid based ntiid and not set until persistent

        scope = sharing.CourseInstanceSharingScope('foo')
        other_scope = sharing.CourseInstanceSharingScope('foo')

        # Scopes are equal to themselves regardless of state
        assert_that(scope, equal_to(scope))

        # We have not ntiid yet
        assert_that(calling(getattr).with_args(scope, 'NTIID'), raises(AttributeError))

        # With no NTIID scopes aren't equal
        assert_that(scope, is_not(equal_to(other_scope)))
        assert_that(scope.__eq__(other_scope), is_(NotImplemented))

        # Scopes without NTIID also can't be hashed
        assert_that(calling(hash).with_args(scope), raises(TypeError))

        # Once a scope has an NTIID it can be hashed, and we do so by ntiid
        scope._v_ntiid = 'tag:nextthought.com'
        assert_that(scope.NTIID, is_('tag:nextthought.com'))
        assert_that(hash(scope), equal_to(hash(scope.NTIID)))

        # scopes with ntiids are equal if their ntiids are equal
        other_scope._v_ntiid = 'tag:foo.com'
        assert_that(scope, is_not(other_scope))

        other_scope._v_ntiid = scope._v_ntiid
        assert_that(scope, is_(other_scope))
        assert_that(scope.NTIID, is_(other_scope.NTIID))


class TestSharingScopePersistence(DataserverLayerTest):

    @WithMockDSTrans
    def test_scope_ntiid(self):
        scope = sharing.CourseInstanceSharingScope('foo')

        # We can't get an ntiid if we aren't in a connection
        assert_that(calling(getattr).with_args(scope, 'NTIID'), raises(AttributeError))

        # Now if we are added to a connection we do have an ntiid
        connection = IConnection(self.ds.root)
        connection.add(scope)
        assert_that(scope.NTIID, starts_with('tag:nextthought.com,2011-10:system-OID'))


import functools

from zope import interface
from zope import component
from zope import lifecycleevent

from zope.annotation.interfaces import IAttributeAnnotatable

from zope.component import eventtesting

from zope.container.interfaces import IContained

from zope.copypastemove import IObjectMover

from zope.security.interfaces import IPrincipal

from persistent import Persistent

from nti.contenttypes.courses import courses

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE

from nti.dataserver.authorization import CONTENT_ROLE_PREFIX
from nti.dataserver.authorization import role_for_providers_content

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IMutableGroupMember

from nti.dataserver.sharing import SharingSourceMixin

from nti.dataserver.users.users import User

from nti.ntiids import ntiids

from nti.schema.eqhash import EqHash

from nti.wref.interfaces import IWeakRef

from nti.contenttypes.courses.tests import CourseLayerTest


@functools.total_ordering
@interface.implementer(IPrincipal, IWeakRef, IContained, IAttributeAnnotatable)
class MockPrincipal(SharingSourceMixin, Persistent):
    username = id = u'MyPrincipal'

    __name__ = None
    __parent__ = None

    def __call__(self):
        return self

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __lt__(self, other):
        if other is not self:
            return True
        return False


@EqHash('ntiid')
class MockContentPackage(object):
    ntiid = u"tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california."


class MockContentPackageBundle(object):

    @property
    def ContentPackages(self):
        return (MockContentPackage(),)


class TestFunctionalSharing(CourseLayerTest):

    principal = None
    course = None
    course2 = None

    def _shared_setup(self):
        principal = MockPrincipal()
        self.ds.root[principal.id] = principal

        # we have to be IUser for the right Community event listeners
        # to fire.
        # Do this after adding to avoid setting up profile indexes, etc
        interface.alsoProvides(principal, IUser)

        admin = courses.CourseAdministrativeLevel()
        self.ds.root['admin'] = admin

        for name in 'course', 'course2':

            course = courses.ContentCourseInstance()
            admin[name] = course
            course.SharingScopes.initScopes()

            bundle = MockContentPackageBundle()
            # bypass field validation
            course.__dict__['ContentPackageBundle'] = bundle
            assert_that(course.ContentPackageBundle,
                        is_(same_instance(bundle)))

            sub = course.SubInstances['child'] = courses.ContentCourseSubInstance(
            )
            sub.__dict__['ContentPackageBundle'] = bundle
            sub.SharingScopes.initScopes()

        self.principal = principal
        self.course = admin['course']
        self.course2 = admin['course2']

    @WithMockDSTrans
    def test_content_roles(self):
        self._shared_setup()

        provider = ntiids.get_provider(MockContentPackage.ntiid)
        specific = ntiids.get_specific(MockContentPackage.ntiid)
        role = role_for_providers_content(provider, specific)

        principal = self.principal
        member = component.getAdapter(principal,
                                      IMutableGroupMember,
                                      CONTENT_ROLE_PREFIX)
        assert_that(list(member.groups), is_empty())

        course = self.course

        manager = interfaces.ICourseEnrollmentManager(course)
        manager.enroll(principal, scope=ES_CREDIT_DEGREE)

        assert_that(list(member.groups), contains(role))

        manager.drop(principal)

        assert_that(list(member.groups), is_empty())

    @WithMockDSTrans
    def test_usernames_of_dynamic_memberships(self):
        self._shared_setup()
        user = User.create_user(username=u"nti@nti.com")

        course = self.course
        manager = interfaces.ICourseEnrollmentManager(course)
        manager.enroll(user, scope=ES_CREDIT_DEGREE)
        degree = course.SharingScopes[ES_CREDIT_DEGREE]
        ntiid = degree.NTIID

        names = list(user.usernames_of_dynamic_memberships)
        assert_that(ntiid, is_in(names))

    @WithMockDSTrans
    def test_purchased(self):
        self._shared_setup()
        principal = self.principal

        course = self.course
        manager = interfaces.ICourseEnrollmentManager(course)
        manager.enroll(principal, scope=ES_PURCHASED)

        public = course.SharingScopes[ES_PUBLIC]
        purchased = course.SharingScopes[ES_PURCHASED]

        assert_that(principal, is_in(public))
        assert_that(principal, is_in(purchased))

    @WithMockDSTrans
    @fudge.patch('nti.contenttypes.courses.utils.get_enrollments')
    def test_sub_and_parent_drop_parent(self, mock_get_enroll):
        self._shared_setup()
        # Need to mock out enrollments since these are mock courses.
        mock_get_enroll.is_callable().returns(())

        provider = ntiids.get_provider(MockContentPackage.ntiid)
        specific = ntiids.get_specific(MockContentPackage.ntiid)
        role = role_for_providers_content(provider, specific)

        principal = self.principal
        member = component.getAdapter(principal,
                                      IMutableGroupMember,
                                      CONTENT_ROLE_PREFIX)
        assert_that(list(member.groups), is_empty())

        course = self.course
        sub_course = self.course.SubInstances['child']

        manager = interfaces.ICourseEnrollmentManager(course)
        manager.enroll(principal, scope=ES_CREDIT_DEGREE)

        public = course.SharingScopes[ES_PUBLIC]
        credit = course.SharingScopes[ES_CREDIT]
        degree = course.SharingScopes[ES_CREDIT_DEGREE]
        ndgree = course.SharingScopes[ES_CREDIT_NONDEGREE]

        assert_that(principal, is_in(public))
        assert_that(principal, is_in(credit))
        assert_that(principal, is_in(degree))
        assert_that(principal, is_not(is_in(ndgree)))

        submanager = interfaces.ICourseEnrollmentManager(sub_course)
        record2 = submanager.enroll(principal, scope=ES_CREDIT_DEGREE)
        assert_that(list(member.groups), contains(role))
        # Drop the parent first; this is mocked for the underlying subscribers
        # of drop.
        mock_get_enroll.is_callable().returns((record2,))
        manager.drop(principal)

        # Unenrolling does not lose our role
        assert_that(list(member.groups), contains(role))

        # and still in the correct scopes
        public = course.SharingScopes[ES_PUBLIC]
        credit = course.SharingScopes[ES_CREDIT]
        degree = course.SharingScopes[ES_CREDIT_DEGREE]
        ndgree = course.SharingScopes[ES_CREDIT_NONDEGREE]

        assert_that(principal, is_in(public))
        assert_that(principal, is_in(credit))
        assert_that(principal, is_in(degree))
        assert_that(principal, is_not(is_in(ndgree)))

        sub_public = sub_course.SharingScopes[ES_PUBLIC]
        sub_credit = sub_course.SharingScopes[ES_CREDIT]
        sub_degree = sub_course.SharingScopes[ES_CREDIT_DEGREE]
        sub_ndgree = sub_course.SharingScopes[ES_CREDIT_NONDEGREE]

        assert_that(principal, is_in(sub_public))
        assert_that(principal, is_in(sub_credit))
        assert_that(principal, is_in(sub_degree))
        assert_that(principal, is_not(is_in(sub_ndgree)))

        mock_get_enroll.is_callable().returns(())
        submanager.drop(principal)
        # Now gone from the roles
        assert_that(list(member.groups), is_empty())

        # and all the scopes
        assert_that(principal, is_not(is_in(public)))
        assert_that(principal, is_not(is_in(credit)))
        assert_that(principal, is_not(is_in(degree)))
        assert_that(principal, is_not(is_in(ndgree)))

        assert_that(principal, is_not(is_in(sub_public)))
        assert_that(principal, is_not(is_in(sub_credit)))
        assert_that(principal, is_not(is_in(sub_degree)))
        assert_that(principal, is_not(is_in(sub_ndgree)))

    @WithMockDSTrans
    def test_change_scope(self):
        self._shared_setup()

        principal = self.principal
        course = self.course

        manager = interfaces.ICourseEnrollmentManager(course)
        record = manager.enroll(principal, scope=ES_CREDIT_DEGREE)

        public = course.SharingScopes[ES_PUBLIC]
        credit = course.SharingScopes[ES_CREDIT]
        purchased = course.SharingScopes[ES_PURCHASED]
        degree = course.SharingScopes[ES_CREDIT_DEGREE]
        ndgree = course.SharingScopes[ES_CREDIT_NONDEGREE]

        assert_that(principal, is_in(public))
        assert_that(principal, is_in(credit))
        assert_that(principal, is_in(degree))
        assert_that(principal, is_in(purchased))
        assert_that(principal, is_not(is_in(ndgree)))

        record.Scope = ES_CREDIT_NONDEGREE
        lifecycleevent.modified(record)

        assert_that(principal, is_in(public))
        assert_that(principal, is_in(credit))
        assert_that(principal, is_in(purchased))
        assert_that(principal, is_not(is_in(degree)))
        assert_that(principal, is_in(ndgree))

        record.Scope = ES_PUBLIC
        lifecycleevent.modified(record)

        assert_that(principal, is_in(public))
        assert_that(principal, is_not(purchased))
        assert_that(principal, is_not(is_in(credit)))
        assert_that(principal, is_not(is_in(degree)))
        assert_that(principal, is_not(is_in(ndgree)))

    @WithMockDSTrans
    def test_change_scope_through_move(self):
        self._shared_setup()

        principal = self.principal
        orig_course = self.course

        manager = interfaces.ICourseEnrollmentManager(orig_course)
        record = manager.enroll(principal, scope=ES_CREDIT_DEGREE)

        public = orig_course.SharingScopes[ES_PUBLIC]
        credit = orig_course.SharingScopes[ES_CREDIT]
        degree = orig_course.SharingScopes[ES_CREDIT_DEGREE]
        ndgree = orig_course.SharingScopes[ES_CREDIT_NONDEGREE]

        assert_that(principal, is_in(public))
        assert_that(principal, is_in(credit))
        assert_that(principal, is_in(degree))
        assert_that(principal, is_not(is_in(ndgree)))

        new_course = self.course2
        from nti.contenttypes.courses.enrollment import IDefaultCourseInstanceEnrollmentStorage

        mover = IObjectMover(record)

        eventtesting.clearEvents()

        mover.moveTo(IDefaultCourseInstanceEnrollmentStorage(new_course))

        # So he left everything from the old course:

        assert_that(principal, is_not(is_in(public)))
        assert_that(principal, is_not(is_in(credit)))
        assert_that(principal, is_not(is_in(degree)))
        assert_that(principal, is_not(is_in(ndgree)))

        # ...and is in the things from the new course

        public = new_course.SharingScopes[ES_PUBLIC]
        credit = new_course.SharingScopes[ES_CREDIT]
        degree = new_course.SharingScopes[ES_CREDIT_DEGREE]
        ndgree = new_course.SharingScopes[ES_CREDIT_NONDEGREE]

        assert_that(principal, is_in(public))
        assert_that(principal, is_in(credit))
        assert_that(principal, is_in(degree))
        assert_that(principal, is_not(is_in(ndgree)))

        # Only the desired events fired
# 		[<zope.lifecycleevent.ObjectMovedEvent object at 0x1066d3e10>,
# 		 <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x1066d3d10>,
# 		 <nti.dataserver.interfaces.StopFollowingEvent object at 0x1066d3fd0>,
# 		 <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x1066d3090>,
# 		 <nti.dataserver.interfaces.StopFollowingEvent object at 0x1066d3110>,
# 		 <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x1066d31d0>,
# 		 <nti.dataserver.interfaces.StopFollowingEvent object at 0x103be2250>,
# 		 <nti.dataserver.interfaces.StopDynamicMembershipEvent object at 0x103be2410>,
# 		 <nti.dataserver.interfaces.StopFollowingEvent object at 0x1066cc810>,
# 		 <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1066cc210>,
# 		 <nti.dataserver.interfaces.EntityFollowingEvent object at 0x1066cc310>,
# 		 <nti.dataserver.interfaces.FollowerAddedEvent object at 0x1066cc150>,
# 		 <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1066cc510>,
# 		 <nti.dataserver.interfaces.EntityFollowingEvent object at 0x1066cc250>,
# 		 <nti.dataserver.interfaces.FollowerAddedEvent object at 0x1066cc410>,
# 		 <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1066cc0d0>,
# 		 <nti.dataserver.interfaces.EntityFollowingEvent object at 0x1066cc4d0>,
# 		 <nti.dataserver.interfaces.FollowerAddedEvent object at 0x1066cc1d0>,
# 		 <nti.dataserver.interfaces.StartDynamicMembershipEvent object at 0x1066cc050>,
# 		 <nti.dataserver.interfaces.EntityFollowingEvent object at 0x1066cc390>,
# 		 <nti.dataserver.interfaces.FollowerAddedEvent object at 0x1066cc3d0>,
# 		 <zope.container.contained.ContainerModifiedEvent object at 0x1066d3f10>,
# 		 <zope.container.contained.ContainerModifiedEvent object at 0x1066d3250>]
        evts = eventtesting.getEvents()
        # XXX Not a good test
        assert_that(evts, has_length(23))

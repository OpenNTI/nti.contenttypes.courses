#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that

# We can simply reuse the dataserver test layer and
# test case because its auto-include mechanism will pull us in too.
# But we define some values in case we need to change this later

from nti.dataserver.tests.mock_dataserver import DataserverTestLayer
from nti.dataserver.tests.mock_dataserver import DataserverLayerTest


class CourseTestLayer(DataserverTestLayer):

    @classmethod
    def setUp(cls):
        pass
    tearDown = setUp
    setUpTest = setUp
    tearDownTest = setUp


class CourseLayerTest(DataserverLayerTest):
    layer = CourseTestLayer


import functools

from zope import interface

from zope.annotation.interfaces import IAttributeAnnotatable

from zope.container.interfaces import IContained

from zope.security.interfaces import IPrincipal

from persistent import Persistent

from nti.dataserver.sharing import SharingSourceMixin

from nti.wref.interfaces import IWeakRef


@functools.total_ordering
@interface.implementer(IPrincipal, IWeakRef, IContained, IAttributeAnnotatable)
class MockPrincipal(SharingSourceMixin, Persistent):
    __name__ = None
    __parent__ = None

    username = id = u'MyPrincipal'

    def __call__(self, **kwargs):
        return self

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __lt__(self, other):
        if other is not self:
            return True
        return False


try:
    from unittest import mock
except ImportError:
    import mock

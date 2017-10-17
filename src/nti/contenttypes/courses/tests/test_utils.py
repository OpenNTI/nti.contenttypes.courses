#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that

from nti.testing.matchers import verifiably_provides

from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import ProxyEnrollmentRecord

from nti.dataserver.tests import mock_dataserver


class TestCourse(mock_dataserver.DataserverLayerTest):

    def test_proxy(self):
        p = ProxyEnrollmentRecord()
        assert_that(p, verifiably_provides(ICourseInstanceEnrollmentRecord))

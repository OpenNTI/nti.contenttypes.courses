#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property

from nti.testing.matchers import verifiably_provides

import os
import simplejson

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.model import CourseDiscussion
from nti.contenttypes.courses.discussions.model import DefaultCourseDiscussions

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from nti.externalization.tests import externalizes


class TestModel(CourseLayerTest):

    def test_model(self):
        assert_that(CourseDiscussion(),
                    verifiably_provides(ICourseDiscussion))

        assert_that(DefaultCourseDiscussions(),
                    verifiably_provides(ICourseDiscussions))

    def test_extenalizes(self):
        assert_that(CourseDiscussion(),
                    externalizes(has_entries(
                        'Class', 'Discussion',
                        'MimeType', 'application/vnd.nextthought.courses.discussion',
                        'body', is_(none()),
                        'scopes', is_(none()),
                        'tags', is_([]))))

    def test_internalize(self):
        path = os.path.join(os.path.dirname(__file__), 'discussion.json')
        with open(path, "r") as fp:
            context = fp.read()
            if isinstance(context, bytes):
                context = context.decode('utf-8')
            source = simplejson.loads(context)

        factory = find_factory_for(source)
        assert_that(factory, is_not(none()))
        obj = factory()
        update_from_external_object(obj, source)
        assert_that(obj,
                    has_property('mimeType',
                                 is_('application/vnd.nextthought.courses.discussion')))
        assert_that(obj, has_property('body', is_not(none())))
        assert_that(obj, has_property('scopes', is_(['All'])))
        assert_that(obj,
                    has_property('title',
                                 is_('U.S.: A Potential Breakthrough in Trans-Pacific Trade Talks')))
        assert_that(obj,
                    has_property('tags', is_(('japan', 'trade', 'pacific'))))

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import contains
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import starts_with
from hamcrest import has_property

import os
import shutil
import tempfile
import simplejson

from zope import component

from nti.cabinet.filer import DirectoryFiler

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.importer import CourseOutlineImporter
from nti.contenttypes.courses.importer import CourseTabPreferencesImporter

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseTabPreferences

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.dataserver.tests import mock_dataserver


class TestImporter(CourseLayerTest):

    def _cleanup(self):
        registry = component.getSiteManager()
        for ntiid, node in list(registry.getUtilitiesFor(ICourseOutlineNode)):
            provided = iface_of_node(node)
            registry.unregisterUtility(provided=provided, name=ntiid)

    @mock_dataserver.WithMockDSTrans
    def test_import_outline(self):
        path = os.path.join(os.path.dirname(__file__),
                            'course_outline.json')
        with open(path, "r") as fp:
            source = fp.read().decode("utf-8")
            ext_obj = simplejson.loads(source)
        # create course and add to connection
        inst = ContentCourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(inst)
        # initialize entry
        entry = ICourseCatalogEntry(inst)
        entry.ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-XYZ'
        # initialize outline
        getattr(inst, 'Outline')
        # do import
        try:
            importer = CourseOutlineImporter()
            importer.load_external(inst, ext_obj)
            # check import
            assert_that(inst.Outline, has_length(14))
            for node in inst.Outline.values():
                assert_that(node,
                            has_property('ntiid',
                                         starts_with('tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-XYZ')))
        finally:
            self._cleanup()

    def test_import_course_tab_preferences(self):
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        shutil.copy(os.path.join(os.path.dirname(__file__), 'course_tab_preferences.json'),
                    os.path.join(tmp_dir, 'course_tab_preferences.json'))
        try:
            inst = ContentCourseInstance()
            filer = DirectoryFiler(tmp_dir)
            exporter = CourseTabPreferencesImporter()
            exporter.process(inst, filer)

            prefs = ICourseTabPreferences(inst)
            assert_that(prefs.names, has_length(3))
            assert_that(prefs.names, has_entries({"activity": "Activity1",
                                                  "info": "Course Info1",
                                                  "lessons": "Lessons1"}))
            assert_that(prefs.order, contains("info", "lessons", "activity"))
        finally:
            shutil.rmtree(tmp_dir)

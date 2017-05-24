#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that
from hamcrest import greater_than

import os
import shutil
import tempfile

from zope import component

from nti.cabinet.filer import DirectoryFiler

from nti.cabinet.mixins import get_file_size

from nti.contentlibrary.filesystem import FilesystemKey
from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses._outline_parser import fill_outline_from_key

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.exporter import CourseOutlineExporter
from nti.contenttypes.courses.exporter import BundlePresentationAssetsExporter

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseOutlineNode

from nti.contenttypes.courses.tests import CourseLayerTest


class TestExporter(CourseLayerTest):

    def _cleanup(self):
        registry = component.getGlobalSiteManager()
        for ntiid, node in list(registry.getUtilitiesFor(ICourseOutlineNode)):
            provided = iface_of_node(node)
            registry.unregisterUtility(provided=provided, name=ntiid)

    def test_export_outline(self):
        path = os.path.join(os.path.dirname(__file__),
                            'TestSynchronizeWithSubInstances',
                            'Spring2014',
                            'Gateway')
        inst = ContentCourseInstance()
        inst.root = FilesystemBucket(name="Gateway")
        inst.root.absolute_path = path

        key = FilesystemKey()
        key.absolute_path = path + '/course_outline.xml'

        outline = inst.Outline
        fill_outline_from_key(outline, key)
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        try:
            filer = DirectoryFiler(tmp_dir)
            exporter = CourseOutlineExporter()
            exporter.export(inst, filer)
            path = os.path.join(tmp_dir, 'course_outline.json')
            assert_that(os.path.exists(path), is_(True))
            assert_that(get_file_size(path), is_(greater_than(0)))
        finally:
            self._cleanup()
            shutil.rmtree(tmp_dir)

    def test_export_presentation_assets(self):
        path = os.path.join(os.path.dirname(__file__),
                            'TestSynchronizeWithSubInstances',
                            'Spring2014',
                            'Gateway')
        inst = ContentCourseInstance()
        inst.root = FilesystemBucket(name="Gateway")
        inst.root.absolute_path = path
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        try:
            filer = DirectoryFiler(tmp_dir)
            exporter = BundlePresentationAssetsExporter()
            exporter.export(inst, filer)
            p201 = 'presentation-assets/shared/v1/instructor-photos/01.png'
            path = os.path.join(tmp_dir, p201)
            assert_that(os.path.exists(path), is_(True))
        finally:
            shutil.rmtree(tmp_dir)

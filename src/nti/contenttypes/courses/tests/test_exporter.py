#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that

import os
import shutil
import tempfile

from nti.cabinet.filer import DirectoryFiler

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.exporter import BundlePresentationAssetsExporter

from nti.contenttypes.courses.tests import CourseLayerTest

class TestExporter(CourseLayerTest):

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

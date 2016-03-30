#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import shutil

from zope import interface

from nti.cabinet.filer import DirectoryFiler

from nti.common.property import Lazy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseExportFiler
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

@interface.implementer(ICourseExportFiler)
class CourseExportFiler(DirectoryFiler):

	def __init__(self, context, path=None):
		super(CourseExportFiler, self).__init__(path)
		self.course = ICourseInstance(context)
		
	@Lazy
	def entry(self):
		return ICourseCatalogEntry(self.course)

	def asZip(self, path=None):
		base_name = path or './'
		base_name = os.path.join(base_name, self.course.__name__)
		if os.path.exists(base_name + ".zip"):
			os.remove(base_name + ".zip")
		result = shutil.make_archive(base_name, 'zip', self.path)
		return result

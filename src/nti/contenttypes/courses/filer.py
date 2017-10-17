#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import shutil
import tempfile

from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.cabinet.filer import DirectoryFiler

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseExportFiler
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.namedfile.file import safe_filename

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseExportFiler)
class CourseExportFiler(DirectoryFiler):

    def __init__(self, context, path=None):
        super(CourseExportFiler, self).__init__(path)
        self.course = ICourseInstance(context)

    @Lazy
    def entry(self):
        return ICourseCatalogEntry(self.course)

    def prepare(self, path=None):
        self.path = path if path else self.path
        if not self.path:
            self.path = tempfile.mkdtemp()
        else:
            self.path = super(CourseExportFiler, self).prepare(self.path)

    def asZip(self, path=None):
        base_name = path or tempfile.mkdtemp()
        base_name = os.path.join(base_name,
                                 safe_filename(self.course.__name__))
        if os.path.exists(base_name + ".zip"):
            os.remove(base_name + ".zip")
        result = shutil.make_archive(base_name, 'zip', self.path)
        return result

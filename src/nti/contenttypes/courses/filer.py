#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import zipfile
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
        """
        We'd prefer to use `shutil.make_archive`, but with python2.7, we cannot
        specify the zip64 extensions without doing so manually.
        """
        base_name = path or tempfile.mkdtemp()
        base_name = os.path.join(base_name,
                                 safe_filename(self.course.__name__))
        zip_filename = base_name + ".zip"
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        with zipfile.ZipFile(zip_filename,
                             "w",
                             zipfile.ZIP_DEFLATED,
                             allowZip64=True) as zf:
            for root, unused_dirnames, filenames in os.walk(self.path):
                for name in filenames:
                    rel_path = os.path.relpath(root, self.path)
                    target_name = os.path.join(rel_path, name)
                    target_name = os.path.normpath(target_name)
                    source_name = os.path.join(root, name)
                    zf.write(source_name, target_name)
        return zip_filename

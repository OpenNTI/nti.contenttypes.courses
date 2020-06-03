#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_properties
does_not = is_not

import io
import os
import json
import shutil
import tempfile
import simplejson

from zope import component

from nti.cabinet.filer import DirectoryFiler
from nti.cabinet.filer import transfer_to_native_file

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.importer import CourseInfoImporter

from nti.contenttypes.courses.tests import CourseCreditLayerTest

from nti.contenttypes.credit.credit import CreditDefinition
from nti.contenttypes.credit.credit import CreditDefinitionContainer

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.credit.interfaces import ICreditDefinitionContainer

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.intid.common import addIntId


class TestImportExport(CourseCreditLayerTest):

    @WithMockDSTrans
    def test_import_export(self):
        path = os.path.join(os.path.dirname(__file__),
                            'course_info.json')
        with open(path, "r") as fp:
            source = fp.read().decode("utf-8")
            ext_obj = simplejson.loads(source)

        root_path = os.path.join(os.path.dirname(__file__),
                                                'TestSynchronizeWithSubInstances',
                                                'Spring2014',
                                                'Gateway')
        # This file will be overwritten later; copy it so it can be restored
        course_info_path = os.path.join(root_path,
                                        'course_info.json')
        with open(course_info_path, "r") as fp:
            old_source = fp.read().decode("utf-8")

        # This extra information should be imported
        ext_obj['awardableCredits'] = [
        {
            "Class": "CourseAwardableCredit",
            "CreatedTime": 1526934001.560927,
            "Last Modified": 1526934001.565191,
            "MimeType": "application/vnd.nextthought.credit.courseawardablecredit",
            "NTIID": "tag:nextthought.com,2011-10:NTI-AwardableCredit-system_20180521202001_561678_1175851886",
            "OID": "tag:nextthought.com,2011-10:system-OID-0x01d29e:5573657273",
            "amount": 1,
            "credit_definition": {
                "Class": "CreditDefinition",
                "CreatedTime": 1526933942.780502,
                "Creator": "bryan.hoke@nextthought.com",
                "Last Modified": 1526933942.780502,
                "MimeType": "application/vnd.nextthought.credit.creditdefinition",
                "NTIID": "tag:nextthought.com,2011-10:NTI-CreditDefinition-system_20180521201902_781279_2616385502",
                "OID": "tag:nextthought.com,2011-10:bryan.hoke@nextthought.com-OID-0x01d298:5573657273:Tqk4xvP71wK",
                "credit_type": "Credit",
                "credit_units": "Hours"
            }
        }]
        tmp_dir = tempfile.mkdtemp()
        json_str = json.dumps(ext_obj)
        json_io = io.BytesIO(json_str)
        export_path = os.path.join(tmp_dir, 'course_info.json')
        export_filer = DirectoryFiler(tmp_dir)

        # Container
        container = CreditDefinitionContainer()
        gsm = component.getGlobalSiteManager()
        gsm.registerUtility(container,
                            ICreditDefinitionContainer)

        # Create course and add to connection
        course = ContentCourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(course)
        connection.add(container)
        course.root = FilesystemBucket(name=u"Gateway")
        course.root.absolute_path = root_path
        # Set up the credit definition
        credit_definition = CreditDefinition(credit_type=u'Credit',
                                             credit_units=u'Hours')
        credit_definition = container.add_credit_definition(credit_definition)
        addIntId(credit_definition)
        try:
            export_filer.save(export_path, json_io, overwrite=True)
            importer = CourseInfoImporter()
            importer.process(course, export_filer)
            catalog_entry = ICourseCatalogEntry(course)
            assert_that(catalog_entry.awardable_credits, has_length(1))
            awardable_credit = catalog_entry.awardable_credits[0]
            assert_that(awardable_credit.ntiid, is_not("tag:nextthought.com,2011-10:NTI-AwardableCredit-system_20180521202001_561678_1175851886"))
            credit_def = awardable_credit.credit_definition
            assert_that(credit_def, is_not(none()))
            assert_that(credit_def.ntiid, is_not("tag:nextthought.com,2011-10:NTI-CreditDefinition-system_20180521201902_781279_2616385502"))
            assert_that(credit_def, has_properties(u'credit_type', u'Credit',
                                                   u'credit_units', u'Hours'))
        finally:
            shutil.rmtree(tmp_dir)
            # Restore the file we overwrote
            transfer_to_native_file(old_source, course_info_path)
            component.getGlobalSiteManager().unregisterUtility(container,
                                                               ICreditDefinitionContainer)

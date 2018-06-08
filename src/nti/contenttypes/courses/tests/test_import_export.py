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
 
from nti.contentlibrary.filesystem import FilesystemBucket 
 
from nti.contenttypes.courses.courses import ContentCourseInstance 
 
from nti.contenttypes.courses.importer import CourseInfoImporter 
 
from nti.contenttypes.courses.tests import CourseCreditLayerTest 
 
from nti.contenttypes.credit.credit import AwardableCredit 
from nti.contenttypes.credit.credit import CreditDefinition 
from nti.contenttypes.credit.credit import CreditDefinitionContainer 
 
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.credit.interfaces import ICreditDefinitionContainer 
 
from nti.dataserver.tests import mock_dataserver 
 
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans 

from nti.intid.common import addIntId
 
 
class TestImportExport(CourseCreditLayerTest): 
     
    def setUp(self): 
        self.container = CreditDefinitionContainer() 
        gsm = component.getGlobalSiteManager() 
        gsm.registerUtility(self.container, 
                            ICreditDefinitionContainer) 
         
    def tearDown(self): 
        gsm = component.getGlobalSiteManager() 
        gsm.unregisterUtility(self.container, 
                              ICreditDefinitionContainer)
     
    def _create_source_data(self, source_course): 
        addIntId()
        self.credit_definition = CreditDefinition(credit_type=u'credit',
                                                  credit_units=u'hours')
        awardable_credit = AwardableCredit() 
        awardable_credit.credit_definition = self.credit_definition 
        source_course.awardable_credits = [awardable_credit] 
     
    @WithMockDSTrans 
    def test_import_export(self):
        path = os.path.join(os.path.dirname(__file__), 
                            'course_info.json') 
        with open(path, "r") as fp: 
            source = fp.read().decode("utf-8") 
            ext_obj = simplejson.loads(source) 
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
        export_filer = DirectoryFiler(tmp_dir) 

        json_str = json.dumps(ext_obj) 
        json_io = io.BytesIO(json_str) 
        export_path = os.path.join(tmp_dir, 'course_info.json') 

        with mock_dataserver.mock_db_trans(self.ds):
            # Create course and add to connection 
            course = ContentCourseInstance()
            connection = mock_dataserver.current_transaction
            connection.add(course)
            connection.add(self.container)
            course.root = FilesystemBucket(name=u"Gateway") 
            course.root.absolute_path = os.path.join(os.path.dirname(__file__), 
                                                     'TestSynchronizeWithSubInstances',
                                                     'Spring2014',
                                                     'Gateway')
            credit_definition = CreditDefinition(credit_type=u'Credit',
                                                 credit_units=u'Hours')
            credit_definition = self.container.add_credit_definition(credit_definition)
            addIntId(credit_definition)
            try: 
                importer = CourseInfoImporter() 
                export_filer.save(export_path, json_io, overwrite=True) 
                importer.process(course, export_filer) 
                catalog_entry = ICourseCatalogEntry(course)
                assert_that(catalog_entry.awardable_credits, has_length(1))
                awardable_credit = catalog_entry.awardable_credits[0]
                credit_def = awardable_credit.credit_definition
                assert_that(credit_def, is_not(none()))
                assert_that(credit_def, has_properties(u'credit_type', u'Credit',
                                                       u'credit_units', u'Hours'))
            finally: 
                shutil.rmtree(tmp_dir) 
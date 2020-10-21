#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904


from hamcrest import has_key
from hamcrest import is_
from hamcrest import contains
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import greater_than

import os
import shutil
import tempfile
import simplejson

from zope import component
from zope import interface

from nti.assessment.interfaces import IQAssessmentDateContext
from nti.assessment.interfaces import IQAssessmentPolicies
from nti.assessment.interfaces import IQEditableEvaluation
from nti.assessment.interfaces import IQInquiry

from nti.cabinet.filer import DirectoryFiler

from nti.cabinet.mixins import get_file_size

from nti.contentlibrary.filesystem import FilesystemKey
from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses._outline_parser import fill_outline_from_key

from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance

from nti.contenttypes.courses.exporter import AssessmentPoliciesExporter
from nti.contenttypes.courses.exporter import CourseOutlineExporter
from nti.contenttypes.courses.exporter import CourseTabPreferencesExporter
from nti.contenttypes.courses.exporter import BundlePresentationAssetsExporter

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseTabPreferences

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.externalization.datetime import datetime_from_string

from nti.ntiids.ntiids import hash_ntiid


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
        inst.root = FilesystemBucket(name=u"Gateway")
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
        inst.root = FilesystemBucket(name=u"Gateway")
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


    def test_export_course_tab_preferences(self):
        path = os.path.join(os.path.dirname(__file__),
                            'TestSynchronizeWithSubInstances',
                            'Spring2014',
                            'Gateway')
        inst = ContentCourseInstance()
        inst.root = FilesystemBucket(name=u"Gateway")
        inst.root.absolute_path = path

        prefs = ICourseTabPreferences(inst)
        prefs.update_names({"1": "a", "2": "b"})
        prefs.update_order(["2", "1"])

        subinst = ContentCourseSubInstance()
        inst.SubInstances[u'child'] = subinst
        prefs = ICourseTabPreferences(subinst)
        prefs.update_names({"2": "c"})

        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        try:
            filer = DirectoryFiler(tmp_dir)
            exporter = CourseTabPreferencesExporter()
            exporter.export(inst, filer)
            path = os.path.join(tmp_dir, "course_tab_preferences.json")
            assert_that(os.path.exists(path), is_(True))
            with open(path, "rb") as f:
                data = simplejson.load(f)
                assert_that(data['names'], has_length(2))
                assert_that(data['names'], has_entries({"1": 'a', "2": 'b'}))
                assert_that(data['order'], contains("2", "1"))

            # verify section
            path = os.path.join(tmp_dir, "Sections/child/course_tab_preferences.json")
            assert_that(os.path.exists(path), is_(True))
            with open(path, "rb") as f:
                data = simplejson.load(f)
                assert_that(data['names'], has_length(1))
                assert_that(data['names'], has_entries({"2": 'c'}))
                assert_that(data['order'], has_length(0))

        finally:
            shutil.rmtree(tmp_dir)

    def test_export_survey_policies(self):
        survey_ntiid = "tag:nextthought.com,2011-10:OU-NAQ-survey_system_4744496732793162703_1679835696"
        salt=b'test_salt'
        expected_survey_ntiid = hash_ntiid(survey_ntiid, salt=salt)
        gsm = component.getGlobalSiteManager()

        @interface.implementer(IQInquiry)
        class FakeSurvey(object):
            pass

        survey = FakeSurvey()
        interface.alsoProvides(survey, IQEditableEvaluation)
        gsm.registerUtility(survey,
                            provided=IQInquiry,
                            name=survey_ntiid)
        try:

            path = os.path.join(os.path.dirname(__file__),
                                'TestSynchronizeWithSubInstances',
                                'Spring2014',
                                'Gateway')
            inst = ContentCourseInstance()
            inst.root = FilesystemBucket(name=u"Gateway")
            inst.root.absolute_path = path

            policies = IQAssessmentPolicies(inst)
            policies.set(survey_ntiid, 'disclosure', 'never')

            date_policies = IQAssessmentDateContext(inst)

            begin_str = '2020-10-12T05:00:00Z'
            begin = datetime_from_string(begin_str)
            date_policies.set(survey_ntiid, 'available_for_submission_beginning', begin)

            end_str = '2024-10-12T05:00:00Z'
            end = datetime_from_string(end_str)
            date_policies.set(survey_ntiid, 'available_for_submission_ending', end)

            subinst = ContentCourseSubInstance()
            inst.SubInstances[u'child'] = subinst
            policies = IQAssessmentPolicies(subinst)
            policies.set(survey_ntiid, 'disclosure', 'always')

            date_policies = IQAssessmentDateContext(subinst)

            sub_begin_str = '2021-10-12T05:00:00Z'
            sub_begin = datetime_from_string(sub_begin_str)
            date_policies.set(survey_ntiid, 'available_for_submission_beginning', sub_begin)

            tmp_dir = tempfile.mkdtemp(dir="/tmp")
            try:
                filer = DirectoryFiler(tmp_dir)
                exporter = AssessmentPoliciesExporter()
                exporter.export(inst, filer, backup=False, salt=salt)
                path = os.path.join(tmp_dir, "assignment_policies.json")
                assert_that(os.path.exists(path), is_(True))
                with open(path, "rb") as f:
                    data = simplejson.load(f)
                    assert_that(data, has_length(1))
                    assert_that(data, has_key(expected_survey_ntiid))
                    assert_that(data[expected_survey_ntiid], has_length(3))
                    assert_that(data[expected_survey_ntiid],
                                has_entries({
                                    'available_for_submission_beginning': begin_str,
                                    'available_for_submission_ending': end_str,
                                    'disclosure': 'never'
                                }))

                # verify section
                path = os.path.join(tmp_dir, "Sections/child/assignment_policies.json")
                assert_that(os.path.exists(path), is_(True))
                with open(path, "rb") as f:
                    data = simplejson.load(f)
                    assert_that(data[expected_survey_ntiid], has_length(2))
                    assert_that(data[expected_survey_ntiid],
                                has_entries({
                                    'available_for_submission_beginning': sub_begin_str,
                                    'disclosure': 'always'
                                }))

            finally:
                shutil.rmtree(tmp_dir)
        finally:
            gsm.unregisterUtility(survey,
                                  provided=IQInquiry,
                                  name=survey_ntiid)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
does_not = is_not

import os
import codecs

import simplejson

from zope import component

from zope.schema.interfaces import TooShort

from nti.contenttypes.courses.credit import CourseAwardableCredit

from nti.contenttypes.courses.internalization import legacy_to_schema_transform

from nti.contenttypes.courses.legacy_catalog import PersistentCourseCatalogLegacyEntry

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.contenttypes.credit.credit import CreditDefinition
from nti.contenttypes.credit.credit import CreditDefinitionContainer

from nti.contenttypes.credit.interfaces import ICreditDefinitionContainer

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.externalization.externalization import toExternalObject

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object


class TestInternalization(CourseLayerTest):

    def setUp(self):
        path = os.path.join(os.path.dirname(__file__),
                            'course_info.json')
        self.path = path
        self.container = CreditDefinitionContainer()
        component.getGlobalSiteManager().registerUtility(self.container,
                                                         ICreditDefinitionContainer)

    @WithMockDSTrans
    def tearDown(self):
        component.getGlobalSiteManager().unregisterUtility(self.container,
                                                           ICreditDefinitionContainer)

    def test_trivial_parse(self):
        with codecs.open(self.path, "r", "utf-8") as fp:
            json_data = simplejson.load(fp)

        json_data = legacy_to_schema_transform(json_data)
        entry = PersistentCourseCatalogLegacyEntry()
        update_from_external_object(entry, json_data)
        ext_obj = toExternalObject(entry)
        assert_that(ext_obj,
                    has_entries('Preview', False,
                                "StartDate", "2016-08-22T05:00:00Z",
                                "EndDate", "2016-12-19T05:00:00Z",
                                "Schedule", has_entries("days", ["MTWRF"],
                                                        "times", has_length(2)),
                                "Instructors", has_length(5),
                                "ProviderUniqueID", "BIOL 2124",
                                "ProviderDepartmentTitle", "Department of Biology, University of Oklahoma",
                                "description", is_not(none()),
                                "Credit", has_length(1),
                                "title", "Human Physiology",
                                "Video", "kaltura://1500101/0_gpczmps5/"))

        update_from_external_object(entry, {'Preview': True})
        assert_that(entry.Preview, is_(True))

    def test_provider_unique_id_trims(self):
        with codecs.open(self.path, "r", "utf-8") as fp:
            json_data = simplejson.load(fp)

        json_data["id"] = u" foo_bar baz    "
        entry = PersistentCourseCatalogLegacyEntry()
        update_from_external_object(entry, json_data)

        assert_that(entry.ProviderUniqueID, is_('foo_bar baz'))

    def test_provider_unique_not_empty(self):
        with codecs.open(self.path, "r", "utf-8") as fp:
            json_data = simplejson.load(fp)

        json_data["id"] = u""
        entry = PersistentCourseCatalogLegacyEntry()
        with self.assertRaises(TooShort):
            update_from_external_object(entry, json_data)

        with codecs.open(self.path, "r", "utf-8") as fp:
            json_data = simplejson.load(fp)

        json_data["id"] = u"    "
        with self.assertRaises(TooShort):
            update_from_external_object(entry, json_data)

    def test_preview_derivation(self):
        entry = PersistentCourseCatalogLegacyEntry()
        with codecs.open(self.path, "r", "utf-8") as fp:
            json_data = simplejson.load(fp)
        json_data.pop('startDate', None)
        json_data.pop('isPreview', None)
        json_data = legacy_to_schema_transform(json_data)
        update_from_external_object(entry, json_data)

        # By default we have no startdate, no explicit Preview
        # so preview is False
        assert_that(entry.StartDate, none())
        assert_that(entry.Preview, is_(False))

        # If our start date is in the past, we are still not in preview
        data = legacy_to_schema_transform({"startDate": "2000-08-22T05:00:00Z"})
        update_from_external_object(entry, data)

        assert_that(entry.StartDate, is_not(none()))
        assert_that(entry.Preview, is_(False))

        # But we can make it explicitly in preview
        data = legacy_to_schema_transform({"Preview": True})
        update_from_external_object(entry, data)

        assert_that(entry.StartDate, is_not(none()))
        assert_that(entry.Preview, is_(True))

        # If we remove the explicit preview setting we are back to being
        # derived by the StartDate
        data = legacy_to_schema_transform({"Preview": None})
        update_from_external_object(entry, data)

        assert_that(entry.StartDate, is_not(none()))
        assert_that(entry.Preview, is_(False))

        # And because we aren't explicitly set a date in the future
        # now has us in preview mode
        data = legacy_to_schema_transform({"startDate": "2050-08-22T05:00:00Z"})
        update_from_external_object(entry, data)

        assert_that(entry.StartDate, is_not(none()))
        assert_that(entry.Preview, is_(True))


class TestAwardableCreditsInternalization(CourseLayerTest):

    def setUp(self):
        path = os.path.join(os.path.dirname(__file__),
                            'course_info.json')
        self.path = path

    @WithMockDSTrans
    def test_awardable_credits(self):
        with codecs.open(self.path, "r", "utf-8") as fp:
            json_data = simplejson.load(fp)

        json_data = legacy_to_schema_transform(json_data)
        entry = PersistentCourseCatalogLegacyEntry()
        update_from_external_object(entry, json_data)
        ext_obj = toExternalObject(entry)
        assert_that(ext_obj,
                    has_entries('Preview', False,
                                "StartDate", "2016-08-22T05:00:00Z",
                                "EndDate", "2016-12-19T05:00:00Z",
                                "Schedule", has_entries("days", ["MTWRF"],
                                                        "times", has_length(2)),
                                "Instructors", has_length(5),
                                "ProviderUniqueID", "BIOL 2124",
                                "ProviderDepartmentTitle", "Department of Biology, University of Oklahoma",
                                "description", is_not(none()),
                                "Credit", has_length(1),
                                "title", "Human Physiology",
                                "Video", "kaltura://1500101/0_gpczmps5/"))

        container = CreditDefinitionContainer()
        component.getGlobalSiteManager().registerUtility(container,
                                                         ICreditDefinitionContainer)
        try:
            credit_definition = CreditDefinition(credit_type=u'Credit',
                                                 credit_units=u'Hours')
            # Add to connection for weak refs
            connection = mock_dataserver.current_transaction
            connection.add(container)
            container[credit_definition.ntiid] = credit_definition

            awardable_credit_ext = {'MimeType': CourseAwardableCredit.mime_type,
                                    'amount': 13,
                                    'scope': 'Public',
                                    'credit_definition': credit_definition.ntiid}
            xx = dict(awardable_credit_ext)

            factory = find_factory_for(awardable_credit_ext)
            assert_that(factory, not_none())
            new_io = factory()
            update_from_external_object(new_io, awardable_credit_ext, require_updater=True)

            update_from_external_object(entry, {'awardable_credits': [xx,]})
            assert_that(entry.awardable_credits, has_length(1))
            credit = entry.awardable_credits[0]
            assert_that(credit.scope, is_('Public'))
            assert_that(credit.amount, is_(13))
            assert_that(credit.credit_definition.ntiid, is_(credit_definition.ntiid))
        finally:
            component.getGlobalSiteManager().unregisterUtility(container,
                                                               ICreditDefinitionContainer)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from hamcrest import same_instance
from hamcrest import has_properties
from hamcrest import contains_string
from hamcrest import contains_inanyorder

import fudge
import os.path
import datetime

from zope import interface
from zope import component

from persistent.interfaces import IPersistent

from nti.contentlibrary import filesystem
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.assessment.interfaces import IQAssignmentDateContext

from nti.assessment.interfaces import IQAssignmentPolicies

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CREATE
from nti.dataserver.interfaces import EVERYONE_GROUP_NAME
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME
from nti.dataserver.interfaces import ISharingTargetEntityIterable

from nti.externalization.externalization import to_external_object

from nti.contenttypes.courses import catalog
from nti.contenttypes.courses import legacy_catalog

from nti.contenttypes.courses.decorators import _AnnouncementsDecorator
from nti.contenttypes.courses.decorators import _SharingScopesAndDiscussionDecorator

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import IEnrollmentMappedCourseInstance

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses._synchronize import synchronize_catalog_from_root

from nti.externalization.tests import externalizes

from nti.dataserver.tests.test_authorization_acl import permits
from nti.dataserver.tests.test_authorization_acl import denies

from nti.testing.matchers import is_empty
from nti.testing.matchers import verifiably_provides

from nti.contenttypes.courses.tests import CourseLayerTest

class TestFunctionalSynchronize(CourseLayerTest):

	def setUp(self):
		self.library = filesystem.GlobalFilesystemContentPackageLibrary(
			os.path.join(os.path.dirname(__file__), 'test_subscribers'))
		self.library.syncContentPackages()
		component.getGlobalSiteManager().registerUtility(self.library, IContentPackageLibrary)

		root_name = 'TestSynchronizeWithSubInstances'
		absolute_path = os.path.join(os.path.dirname(__file__),
									  root_name)
		bucket = filesystem.FilesystemBucket(name=root_name)
		bucket.absolute_path = absolute_path

		folder = catalog.CourseCatalogFolder()

		self.folder = folder
		self.bucket = bucket

	def tearDown(self):
		component.getGlobalSiteManager().unregisterUtility(self.library, IContentPackageLibrary)

	def test_synchronize_with_sub_instances(self):
		bucket = self.bucket
		folder = self.folder

		synchronize_catalog_from_root(folder, bucket)

		# Now check that we get the structure we expect
		spring = folder['Spring2014']
		gateway = spring['Gateway']

		# Define our scope ntiids
		public_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-public'
		restricted_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-restricted'
		gateway.SharingScopes['Public'].to_external_ntiid_oid = lambda: public_ntiid
		gateway.SharingScopes['ForCredit'].to_external_ntiid_oid = lambda: restricted_ntiid

		assert_that(gateway, verifiably_provides(IEnrollmentMappedCourseInstance))
		assert_that(gateway, externalizes())

		assert_that(gateway.Outline, has_length(7))

		assert_that(gateway.ContentPackageBundle.__parent__,
					 is_(gateway))

		# The bundle's NTIID is derived from the path
		assert_that(gateway.ContentPackageBundle,
					 has_property('ntiid', 'tag:nextthought.com,2011-10:NTI-Bundle:CourseBundle-Spring2014_Gateway'))
		# The name is currently an alias of the NTIID; that's not
		# exactly what we want, but unless/until it's an issue, we'll
		# ignore that.
		assert_that(gateway.ContentPackageBundle,
					 has_property('__name__', gateway.ContentPackageBundle.ntiid))

		# assert_that( gateway.instructors, is_((IPrincipal('harp4162'),)))

		assert_that(ICourseInstanceVendorInfo(gateway),
					 has_entry('OU', has_entry('key', 42)))

		assert_that(ICourseCatalogEntry(gateway),
					 has_properties( 'ProviderUniqueID', 'CLC 3403',
									 'Title', 'Law and Justice',
									 'creators', ('Jason',)))
		assert_that(ICourseInstance(ICourseCatalogEntry(gateway)),
					 is_(gateway))

		assert_that(ICourseCatalogEntry(gateway),
					 verifiably_provides(IPersistent))
		# Ensure we're not proxied
		assert_that(type(ICourseCatalogEntry(gateway)),
					 is_(same_instance(legacy_catalog._CourseInstanceCatalogLegacyEntry)))

		sec1 = gateway.SubInstances['01']
		sec_public_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-public-sec'
		sec_restricted_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-restricted-sec'
		sec1.SharingScopes['Public'].to_external_ntiid_oid = lambda: sec_public_ntiid
		sec1.SharingScopes['ForCredit'].to_external_ntiid_oid = lambda: sec_restricted_ntiid

		assert_that(ICourseInstanceVendorInfo(sec1),
					 has_entry('OU', has_entry('key2', 72)))

		assert_that(sec1.ContentPackageBundle,
					is_(gateway.ContentPackageBundle))

		assert_that(sec1.Outline, is_(gateway.Outline))

		for o in sec1.SharingScopes[ES_CREDIT], gateway.SharingScopes[ES_CREDIT]:
			assert_that(o, verifiably_provides(ISharingTargetEntityIterable))

		# partially overridden course info
		sec1_cat = ICourseCatalogEntry(sec1)
		assert_that(sec1_cat,
					 has_property('key',
								   is_(bucket.getChildNamed('Spring2014')
									   .getChildNamed('Gateway')
									   .getChildNamed('Sections')
									   .getChildNamed('01')
									   .getChildNamed('course_info.json'))))
		assert_that(sec1_cat,
					 is_not(same_instance(ICourseCatalogEntry(gateway))))
		assert_that(sec1_cat,
					 is_(legacy_catalog._CourseSubInstanceCatalogLegacyEntry))
		assert_that(sec1_cat,
					 has_properties('ProviderUniqueID', 'CLC 3403-01',
									'Title', 'Law and Justice',
									'creators', ('Steve',)))
		assert_that(sec1_cat,
					 has_property('PlatformPresentationResources',
								  contains(has_property('root',
														 has_property('absolute_path',
																	  contains_string('Sections/01'))))))

		assert_that(sec1_cat, has_property('links',
											 contains(has_property('target', sec1))))

		gateway.SharingScopes['Public']._v_ntiid = 'gateway-public'
		sec1.SharingScopes['Public']._v_ntiid = 'section1-public'
		sec1.SharingScopes['ForCredit']._v_ntiid = 'section1-forcredit'
		assert_that(sec1,
					 externalizes(has_entries(
						 'Class', 'CourseInstance')))

		gateway_ext = to_external_object(gateway)
		sec1_ext = to_external_object(sec1)
		dec = _SharingScopesAndDiscussionDecorator(sec1, None)
		dec._is_authenticated = False
		dec._do_decorate_external(sec1, sec1_ext)
		dec._do_decorate_external(gateway, gateway_ext)
		assert_that(gateway_ext, has_entry('LegacyScopes',
											has_entries('public', gateway.SharingScopes['Public'].NTIID,
														'restricted', gateway.SharingScopes['ForCredit'].NTIID)))
		assert_that(gateway_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403 - Open')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID)))

		assert_that(sec1_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 # public initially copied from the parent
							 'public', gateway.SharingScopes['Public'].NTIID,
							 'restricted', sec1.SharingScopes['ForCredit'].NTIID)))

		assert_that(sec1_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403-01 - Open')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID)))

		# although if we make the parent non-public, we go back to ourself
		interface.alsoProvides(gateway, INonPublicCourseInstance)
		sec1_ext = to_external_object(sec1)
		dec._do_decorate_external(sec1, sec1_ext)
		assert_that(sec1_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 'public', sec1.SharingScopes['Public'].NTIID,
							 'restricted', sec1.SharingScopes['ForCredit'].NTIID)))
		interface.noLongerProvides(gateway, INonPublicCourseInstance)

		assert_that(sec1_cat,
					 externalizes(has_key('PlatformPresentationResources')))
		assert_that(sec1_cat,
					 # there, but not meaningful yet
					 externalizes(has_entry('CourseNTIID', none())))

		sec2 = gateway.SubInstances['02']
		assert_that(sec2.Outline, has_length(1))

		date_context = IQAssignmentDateContext(sec2)
		assert_that(date_context, has_property('_mapping',
												has_entry(
													"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle",
													has_entry('available_for_submission_beginning',
															  datetime.datetime(2014, 1, 22, 6, 0)))))

		policies = IQAssignmentPolicies(sec2)
		assert_that(policies, has_property('_mapping',
											has_entry(
												"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle",
												is_({'auto_grade': {'total_points': 20}, "maximum_time_allowed": 50}))))
		assert_that(policies.getPolicyForAssignment("tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle"),
					 is_({'auto_grade': {'total_points': 20}, u'maximum_time_allowed': 50}))

		sec2_ext = to_external_object(sec2)
		dec._do_decorate_external(sec2, sec2_ext)
		assert_that(sec2_ext, has_entries(
			'SharingScopes',
			has_entry('Items', has_entry("Public",
										 has_entries('alias', "From Vendor Info",
													 "realname", "Law and Justice - Open",
													 "avatarURL", '/foo/bar.jpg')))))

		# We should have the catalog functionality now
		sec3 = gateway.SubInstances['03']
		cat_entries = list(folder.iterCatalogEntries())
		assert_that(cat_entries, has_length(4))
		assert_that(cat_entries,
					 contains_inanyorder(ICourseCatalogEntry(gateway),
										  ICourseCatalogEntry(sec1),
										  ICourseCatalogEntry(sec2),
										  ICourseCatalogEntry(sec3)))

		# The NTIIDs are derived from the path
		assert_that(cat_entries,
					 contains_inanyorder(
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway_SubInstances_02'),
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway_SubInstances_01'),
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway_SubInstances_03'),
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway')))

		# And each entry can be resolved by ntiid...
		from nti.ntiids import ntiids
		assert_that([ntiids.find_object_with_ntiid(x.ntiid) for x in cat_entries],
					 is_([None, None, None, None]))
		# ...but only with the right catalog installed
		old_cat = component.getUtility(ICourseCatalog)
		component.provideUtility(folder, ICourseCatalog)
		try:
			assert_that([ntiids.find_object_with_ntiid(x.ntiid) for x in cat_entries],
						 is_(cat_entries))
		finally:
			component.provideUtility(old_cat, ICourseCatalog)

		# course discussions
		discussions = ICourseDiscussions(gateway, None)
		assert_that(discussions, is_not(none()))
		assert_that(discussions, has_key('d0.json'))
		assert_that(discussions['d0.json'], has_property('id', is_(u'nti-course-bundle://Discussions/d0.json')))

		discussions = ICourseDiscussions(sec2, None)
		assert_that(discussions, is_not(none()))
		assert_that(discussions, has_key('d1.json'))
		assert_that(discussions['d1.json'], has_property('id', is_(u'nti-course-bundle://Sections/02/Discussions/d1.json')))

	def test_default_sharing_scope_use_parent(self):
		"""
		Verify if the 'UseParentDefaultSharingScope' is set in the section, the
		parent's default scope is used.
		"""
		bucket = self.bucket
		folder = self.folder
		synchronize_catalog_from_root(folder, bucket)

		spring = folder['Spring2014']
		gateway = spring['Gateway']
		# Section 01 tests the non-case; Section 02 verifies toggle;
		# Section 3 verifies negative case.
		sec = gateway.SubInstances['02']

		# Define our scope ntiids
		public_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-public'
		restricted_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-restricted'
		gateway.SharingScopes['Public'].to_external_ntiid_oid = lambda: public_ntiid
		gateway.SharingScopes['ForCredit'].to_external_ntiid_oid = lambda: restricted_ntiid

		sec_public_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-public-sec'
		sec_restricted_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-restricted-sec'
		sec.SharingScopes['Public'].to_external_ntiid_oid = lambda: sec_public_ntiid
		sec.SharingScopes['ForCredit'].to_external_ntiid_oid = lambda: sec_restricted_ntiid

		gateway_ext = to_external_object(gateway)
		sec2_ext = to_external_object(sec)
		dec = _SharingScopesAndDiscussionDecorator(sec, None)
		dec._is_authenticated = False
		dec._do_decorate_external(sec, sec2_ext)
		dec._do_decorate_external(gateway, gateway_ext)

		assert_that(gateway_ext, has_entry('LegacyScopes',
											has_entries('public', gateway.SharingScopes['Public'].NTIID,
														'restricted', gateway.SharingScopes['ForCredit'].NTIID)))

		assert_that(gateway_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403 - Open')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID)))

		assert_that(sec2_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 # public initially copied from the parent
							 'public', gateway.SharingScopes['Public'].NTIID,
							 'restricted', sec.SharingScopes['ForCredit'].NTIID)))

		# Our ForCredit section actually defaults to the parent Public scope
		assert_that(sec2_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'From Vendor Info')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID)))

	@fudge.patch('nti.contenttypes.courses.decorators.IEntityContainer',
				 'nti.app.renderers.decorators.get_remote_user')
	def test_default_sharing_scope_do_not_use_parent(self, mock_container, mock_rem_user):
		"""
		Verify if the 'UseParentDefaultSharingScope' is set to False, the
		parent's default scope is *not* used.
		"""
		# Make sure we're enrolled in sec03
		class Container(object):
			def __contains__(self, o): return True

		mock_container.is_callable().returns(Container())
		mock_rem_user.is_callable().returns(object())

		bucket = self.bucket
		folder = self.folder
		synchronize_catalog_from_root(folder, bucket)

		spring = folder['Spring2014']
		gateway = spring['Gateway']
		# Section 01 tests the non-case; Section 02 verifies toggle;
		# Section 3 verifies negative case.
		sec = gateway.SubInstances['03']

		# Define our scope ntiids
		public_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-public'
		restricted_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-restricted'
		gateway.SharingScopes['Public'].to_external_ntiid_oid = lambda: public_ntiid
		gateway.SharingScopes['ForCredit'].to_external_ntiid_oid = lambda: restricted_ntiid

		sec_public_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-public-sec'
		sec_restricted_ntiid = 'tag:nextthought.com,2011-10:NTI-OID-0x12345-restricted-sec'
		sec.SharingScopes['Public'].to_external_ntiid_oid = lambda: sec_public_ntiid
		sec.SharingScopes['ForCredit'].to_external_ntiid_oid = lambda: sec_restricted_ntiid

		gateway_ext = to_external_object(gateway)
		sec_ext = to_external_object(sec)
		dec = _SharingScopesAndDiscussionDecorator(sec, None)
		dec._is_authenticated = True

		dec._do_decorate_external(sec, sec_ext)
		dec._do_decorate_external(gateway, gateway_ext)

		assert_that(gateway_ext, has_entry('LegacyScopes',
											has_entries('public', gateway.SharingScopes['Public'].NTIID,
														'restricted', gateway.SharingScopes['ForCredit'].NTIID)))

		assert_that(gateway_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403 - Open')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['ForCredit'].NTIID)))

		assert_that(sec_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 # public initially copied from the parent
							 'public', gateway.SharingScopes['Public'].NTIID,
							 'restricted', sec.SharingScopes['ForCredit'].NTIID)))

		# This default comes from our section.
		assert_that(sec_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'From Vendor Info')),
						'DefaultSharingScopeNTIID', sec.SharingScopes['ForCredit'].NTIID)))

	def test_synchronize_clears_caches(self):
		# User.create_user(self.ds, username='harp4162')
		bucket = self.bucket
		folder = self.folder

		assert_that(list(folder.iterCatalogEntries()),
					 is_empty())

		synchronize_catalog_from_root(folder, bucket)


		assert_that(list(folder.iterCatalogEntries()),
					 has_length(4))


		# Now delete the course
		del folder['Spring2014']['Gateway']

		# and the entries are gone
		assert_that(list(folder.iterCatalogEntries()),
					 is_empty())

	def test_non_public_parent_course_doesnt_hide_child_section(self):
		bucket = self.bucket
		folder = self.folder

		synchronize_catalog_from_root(folder, bucket)

		# Now check that we get the structure we expect
		spring = folder['Spring2014']

		gateway = spring['Gateway']

		interface.alsoProvides(gateway, INonPublicCourseInstance)
		cat = ICourseCatalogEntry(gateway)

		sec1 = gateway.SubInstances['01']
		sec1_cat = ICourseCatalogEntry(sec1)

		assert_that(sec1_cat, permits(AUTHENTICATED_GROUP_NAME, ACT_READ))
		assert_that(sec1_cat, permits(AUTHENTICATED_GROUP_NAME, ACT_CREATE))

		# and as joint, just because
		assert_that(sec1_cat, permits([EVERYONE_GROUP_NAME, AUTHENTICATED_GROUP_NAME],
									   ACT_READ))

		# But the CCE for the course is not public
		assert_that(cat, denies(AUTHENTICATED_GROUP_NAME, ACT_READ))
		assert_that(cat, denies(AUTHENTICATED_GROUP_NAME, ACT_CREATE))
		
		# and as joint, just because
		assert_that(cat, denies([EVERYONE_GROUP_NAME, AUTHENTICATED_GROUP_NAME],
								ACT_READ))

	@fudge.patch('nti.contenttypes.courses.decorators.IEntityContainer',
				 'nti.app.renderers.decorators.get_remote_user')
	def test_course_announcements_externalizes(self, mock_container, mock_rem_user):
		"""
		Verify course announcements are externalized on the course.
		"""
		# Mock we have a user and they are in a scope
		class Container(object):
			def __contains__(self, o): return True
		mock_container.is_callable().returns(Container())
		mock_rem_user.is_callable().returns(object())

		bucket = self.bucket
		folder = self.folder
		synchronize_catalog_from_root(folder, bucket)

		spring = folder['Spring2014']
		gateway = spring['Gateway']
		section = gateway.SubInstances['03']
		gateway_discussions = getattr(gateway, 'Discussions')

		section_discussions = section.Discussions
		# Setup. Just make sure we have a discussion here.
		section_discussions['booya'] = gateway_discussions['Forum']

		gateway_ext = {}
		section_ext = {}

		decorator = _AnnouncementsDecorator(gateway, None)
		decorator._do_decorate_external(gateway, gateway_ext)
		decorator = _AnnouncementsDecorator(section, None)
		decorator._is_authenticated = True
		decorator._do_decorate_external(section, section_ext)

		# Gateway does not have announcements since it does not have any.
		assert_that(gateway_ext,
					is_not(has_entries(
								'AnnouncementForums',
								has_entries('Items', is_empty()))))

		# Our section has only open announcements.
		assert_that(section_ext,
					has_entries(
								'AnnouncementForums',
								has_entries('Items',
											has_entry('Public', not_none()),
										   	'Class',
										   	'CourseInstanceAnnouncementForums')))

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

from zope import interface

from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_not
from hamcrest import none
from hamcrest import same_instance
from hamcrest import has_length
from hamcrest import has_entry
from hamcrest import has_entries
from hamcrest import has_properties
from hamcrest import contains_inanyorder
from hamcrest import has_property
from hamcrest import contains
from hamcrest import contains_string
from hamcrest import has_key
from hamcrest import has_item

import datetime

from nti.testing.matchers import verifiably_provides
from nti.testing.matchers import is_empty

import os.path

from .. import catalog
from .. import legacy_catalog
from .._synchronize import synchronize_catalog_from_root
from ..interfaces import ICourseInstanceVendorInfo
from ..interfaces import ICourseCatalogEntry
from ..interfaces import ICourseInstance
from ..interfaces import IEnrollmentMappedCourseInstance
from ..interfaces import ES_CREDIT
from ..interfaces import INonPublicCourseInstance

from nti.contentlibrary import filesystem
from nti.contentlibrary.library import EmptyLibrary
from nti.contentlibrary.interfaces import IContentPackageLibrary
from zope import component
from persistent.interfaces import IPersistent

from . import CourseLayerTest
from nti.externalization.tests import externalizes

from nti.assessment.interfaces import IQAssignmentDateContext
from nti.assessment.interfaces import IQAssignmentPolicies
from nti.dataserver.interfaces import ISharingTargetEntityIterable


from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME
from nti.dataserver.interfaces import EVERYONE_GROUP_NAME
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CREATE

from nti.dataserver.tests.test_authorization_acl import permits
from nti.dataserver.tests.test_authorization_acl import denies

class TestFunctionalSynchronize(CourseLayerTest):

	def setUp(self):
		self.library = EmptyLibrary()
		component.getGlobalSiteManager().registerUtility(self.library, IContentPackageLibrary)
		self.library.syncContentPackages()

		root_name ='TestSynchronizeWithSubInstances'
		absolute_path = os.path.join( os.path.dirname( __file__ ),
									  root_name )
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

		assert_that( gateway, verifiably_provides(IEnrollmentMappedCourseInstance) )
		assert_that( gateway, externalizes())

		assert_that( gateway.Outline, has_length(6) )

		assert_that( gateway.ContentPackageBundle.__parent__,
					 is_(gateway))

		# The bundle's NTIID is derived from the path
		assert_that( gateway.ContentPackageBundle,
					 has_property('ntiid', 'tag:nextthought.com,2011-10:NTI-Bundle:CourseBundle-Spring2014_Gateway'))
		# The name is currently an alias of the NTIID; that's not
		# exactly what we want, but unless/until it's an issue, we'll
		# ignore that.
		assert_that( gateway.ContentPackageBundle,
					 has_property('__name__', gateway.ContentPackageBundle.ntiid) )

		#assert_that( gateway.instructors, is_((IPrincipal('harp4162'),)))

		assert_that( ICourseInstanceVendorInfo(gateway),
					 has_entry( 'OU', has_entry('key', 42) ) )

		assert_that( ICourseCatalogEntry(gateway),
					 has_properties( 'ProviderUniqueID', 'CLC 3403',
									 'Title', 'Law and Justice',
									 'creators', ('Jason',)) )
		assert_that( ICourseInstance(ICourseCatalogEntry(gateway)),
					 is_(gateway) )

		assert_that( ICourseCatalogEntry(gateway),
					 verifiably_provides(IPersistent))
		# Ensure we're not proxied
		assert_that( type(ICourseCatalogEntry(gateway)),
					 is_(same_instance(legacy_catalog._CourseInstanceCatalogLegacyEntry)) )

		sec1 = gateway.SubInstances['01']
		assert_that( ICourseInstanceVendorInfo(sec1),
					 has_entry( 'OU', has_entry('key2', 72) ) )

		assert_that(sec1.ContentPackageBundle,
					is_(gateway.ContentPackageBundle))

		assert_that(sec1.Outline, is_(gateway.Outline))

		for o in sec1.SharingScopes[ES_CREDIT], gateway.SharingScopes[ES_CREDIT]:
			assert_that(o, verifiably_provides(ISharingTargetEntityIterable))

		# partially overridden course info
		sec1_cat = ICourseCatalogEntry(sec1)
		assert_that( sec1_cat,
					 has_property( 'key',
								   is_(bucket.getChildNamed('Spring2014')
									   .getChildNamed('Gateway')
									   .getChildNamed('Sections')
									   .getChildNamed('01')
									   .getChildNamed('course_info.json'))))
		assert_that( sec1_cat,
					 is_not(same_instance(ICourseCatalogEntry(gateway))))
		assert_that( sec1_cat,
					 is_(legacy_catalog._CourseSubInstanceCatalogLegacyEntry))
		assert_that( sec1_cat,
					 has_properties( 'ProviderUniqueID', 'CLC 3403-01',
									 'Title', 'Law and Justice',
									 'creators', ('Steve',)) )
		assert_that( sec1_cat,
					 has_property('PlatformPresentationResources',
								  contains( has_property('root',
														 has_property('absolute_path',
																	  contains_string('Sections/01'))))))

		assert_that( sec1_cat, has_property( 'links',
											 contains(has_property('target', sec1))))

		gateway.SharingScopes['Public']._v_ntiid = 'gateway-public'
		sec1.SharingScopes['Public']._v_ntiid = 'section1-public'
		sec1.SharingScopes['ForCredit']._v_ntiid = 'section1-forcredit'
		assert_that( sec1,
					 externalizes( has_entries(
						 'Class', 'CourseInstance') ) )


		from nti.externalization.externalization import to_external_object
		gateway_ext = to_external_object(gateway)
		sec1_ext = to_external_object(sec1)
		from ..decorators import _SharingScopesAndDiscussionDecorator
		dec = _SharingScopesAndDiscussionDecorator(sec1, None)
		dec._is_authenticated = False
		dec._do_decorate_external(sec1, sec1_ext)
		dec._do_decorate_external(gateway, gateway_ext)
		assert_that( gateway_ext, has_entry('LegacyScopes',
											has_entries('public', gateway.SharingScopes['Public'].NTIID,
														'restricted', gateway.SharingScopes['ForCredit'].NTIID)) )
		assert_that( gateway_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403 - Open') ),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID) ) )

		assert_that( sec1_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 # public initially copied from the parent
							 'public', gateway.SharingScopes['Public'].NTIID,
							 'restricted', sec1.SharingScopes['ForCredit'].NTIID)) )

		assert_that( sec1_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403-01 - Open') ),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID) ) )


		# although if we make the parent non-public, we go back to ourself
		interface.alsoProvides(gateway, INonPublicCourseInstance)
		sec1_ext = to_external_object(sec1)
		dec._do_decorate_external(sec1, sec1_ext)
		assert_that( sec1_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 'public', sec1.SharingScopes['Public'].NTIID,
							 'restricted', sec1.SharingScopes['ForCredit'].NTIID)) )
		interface.noLongerProvides(gateway, INonPublicCourseInstance)


		assert_that( sec1_cat,
					 externalizes( has_key('PlatformPresentationResources')))
		assert_that( sec1_cat,
					 # there, but not meaningful yet
					 externalizes( has_entry('CourseNTIID', none() ) ) )

		sec2 = gateway.SubInstances['02']
		assert_that( sec2.Outline, has_length(1) )

		date_context = IQAssignmentDateContext(sec2)
		assert_that( date_context, has_property('_mapping',
												has_entry(
													"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle",
													has_entry('available_for_submission_beginning',
															  datetime.datetime(2014, 1, 22, 6, 0) ) ) ) )

		policies = IQAssignmentPolicies(sec2)
		assert_that( policies, has_property('_mapping',
											has_entry(
												"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle",
												is_( {'auto_grade': {'total_points': 20}} ) ) ) )
		assert_that( policies.getPolicyForAssignment("tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle"),
					 is_( {'auto_grade': {'total_points': 20}} ) )

		sec2_ext = to_external_object(sec2)
		dec._do_decorate_external(sec2, sec2_ext)
		assert_that(sec2_ext, has_entries(
			'SharingScopes',
			has_entry('Items', has_entry("Public",
										 has_entries('alias', "From Vendor Info",
													 "realname", "Law and Justice - Open",
													 "avatarURL", '/foo/bar.jpg')))))

		# We should have the catalog functionality now

		cat_entries = list(folder.iterCatalogEntries())
		assert_that( cat_entries, has_length(3) )
		assert_that( cat_entries,
					 contains_inanyorder( ICourseCatalogEntry(gateway),
										  ICourseCatalogEntry(sec1),
										  ICourseCatalogEntry(sec2)))

		# The NTIIDs are derived from the path
		assert_that( cat_entries,
					 contains_inanyorder(
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway_SubInstances_02'),
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway_SubInstances_01'),
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway')) )

	def test_synchronize_clears_caches(self):
		#User.create_user(self.ds, username='harp4162')
		bucket = self.bucket
		folder = self.folder

		assert_that( list(folder.iterCatalogEntries()),
					 is_empty() )

		synchronize_catalog_from_root(folder, bucket)


		assert_that( list(folder.iterCatalogEntries()),
					 has_length(3) )


		# Now delete the course
		del folder['Spring2014']['Gateway']

		# and the entries are gone
		assert_that( list(folder.iterCatalogEntries()),
					 is_empty() )

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


		assert_that( sec1_cat, permits(AUTHENTICATED_GROUP_NAME,
									   ACT_READ))
		assert_that( sec1_cat, permits(AUTHENTICATED_GROUP_NAME,
									   ACT_CREATE))
		# and as joint, just because
		assert_that( sec1_cat, permits([EVERYONE_GROUP_NAME,AUTHENTICATED_GROUP_NAME],
									   ACT_READ))

		# But the CCE for the course is not public
		assert_that( cat, denies(AUTHENTICATED_GROUP_NAME,
									   ACT_READ))
		assert_that( cat, denies(AUTHENTICATED_GROUP_NAME,
									   ACT_CREATE))
		# and as joint, just because
		assert_that( cat, denies([EVERYONE_GROUP_NAME,AUTHENTICATED_GROUP_NAME],
									   ACT_READ))

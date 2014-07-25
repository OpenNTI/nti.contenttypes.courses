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


from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_not
from hamcrest import same_instance
from hamcrest import has_length
from hamcrest import has_entry
from hamcrest import has_properties
from hamcrest import contains_inanyorder
from hamcrest import has_property
from hamcrest import contains
from hamcrest import contains_string
from hamcrest import has_key

import datetime

from nti.testing.matchers import verifiably_provides

import os.path

from .. import catalog
from .. import legacy_catalog
from .._synchronize import synchronize_catalog_from_root
from ..interfaces import ICourseInstanceVendorInfo
from ..interfaces import ICourseCatalogEntry
from ..interfaces import ICourseInstance

from nti.contentlibrary import filesystem
from nti.contentlibrary.library import EmptyLibrary
from nti.contentlibrary.interfaces import IContentPackageLibrary
from zope import component
from persistent.interfaces import IPersistent

from . import CourseLayerTest
from nti.externalization.tests import externalizes

from nti.assessment.interfaces import IQAssignmentDateContext



class TestFunctionalSynchronize(CourseLayerTest):

	def setUp(self):
		self.library = EmptyLibrary()
		component.getGlobalSiteManager().registerUtility(self.library, IContentPackageLibrary)
		self.library.syncContentPackages()

	def tearDown(self):
		component.getGlobalSiteManager().unregisterUtility(self.library, IContentPackageLibrary)

	def test_synchronize_with_sub_instances(self):
		#User.create_user(self.ds, username='harp4162')
		root_name ='TestSynchronizeWithSubInstances'
		absolute_path = os.path.join( os.path.dirname( __file__ ),
									  root_name )
		bucket = filesystem.FilesystemBucket(name=root_name)
		bucket.absolute_path = absolute_path

		folder = catalog.CourseCatalogFolder()


		synchronize_catalog_from_root(folder, bucket)

		# Now check that we get the structure we expect
		spring = folder['Spring2014']
		gateway = spring['Gateway']

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

		assert_that( sec1,
					 externalizes( has_entry(
						 'Class', 'CourseInstance' ) ) )

		from nti.externalization.externalization import to_external_object

		to_external_object(sec1_cat)
		assert_that( sec1_cat,
					 externalizes( has_key('PlatformPresentationResources')))

		sec2 = gateway.SubInstances['02']
		assert_that( sec2.Outline, has_length(1) )

		date_context = IQAssignmentDateContext(sec2)
		assert_that( date_context, has_property('_mapping',
												has_entry(
													"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle",
													has_entry('available_for_submission_beginning',
															  datetime.datetime(2014, 1, 22, 6, 0) ) ) ) )

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

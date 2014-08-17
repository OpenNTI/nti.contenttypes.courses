#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904


from hamcrest import assert_that
from hamcrest import is_
from hamcrest import has_property
from hamcrest import has_entry
from hamcrest import has_key
from hamcrest import is_not as does_not
from hamcrest import has_entries
from hamcrest import not_none
from hamcrest import same_instance
from hamcrest import all_of

from nti.testing import base
from nti.testing import matchers

from nti.testing.matchers import verifiably_provides
from nti.externalization.tests import externalizes


from .. import courses
from .. import interfaces

from . import CourseLayerTest
import fudge

class TestCourseInstance(CourseLayerTest):


	def test_course_implements(self):
		assert_that( courses.CourseInstance(), verifiably_provides(interfaces.ICourseInstance) )

	def test_course_containment(self):
		inst = courses.CourseInstance()
		parent = courses.CourseAdministrativeLevel()
		parent['Course'] = inst
		gp = courses.CourseAdministrativeLevel()
		gp['Child'] = parent
		assert_that( gp, verifiably_provides(interfaces.ICourseAdministrativeLevel) )

	def test_course_instance_discussion(self):

		assert_that( courses.CourseInstance(), has_property( 'Discussions', not_none() ) )
		inst = courses.CourseInstance()
		assert_that( inst.Discussions, is_( same_instance( inst.Discussions )))


	def test_course_externalizes(self):

		inst = courses.CourseInstance()
		getattr(inst, 'Discussions' ) # this creates the Public scope
		getattr(inst, 'SubInstances')
		ntiid =  'tag:nextthought.com,2011-10:NTI-OID-0x12345'
		inst.SharingScopes['Public'].to_external_ntiid_oid = lambda: ntiid

		assert_that( unicode(inst.SharingScopes['Public']),
					 is_(ntiid))
		assert_that( inst,
					 externalizes(has_entries('Class', 'CourseInstance',
											  'Discussions', has_entries('Class', 'CommunityBoard', # Reall course instance board
																		 'MimeType', 'application/vnd.nextthought.forums.communityboard',
																		 'title', 'Discussions',
																		 'Creator', ntiid,
																	 ),
											  'MimeType', 'application/vnd.nextthought.courses.courseinstance',
							  ) ) )

		assert_that( inst,
					 externalizes( all_of(
						 does_not( has_key('SubInstances')),
						 # No sharing scopes, no request
						 does_not( has_key('SharingScopes'))) ) )

	@fudge.patch('nti.contenttypes.courses.decorators.IEntityContainer',
				 'nti.app.renderers.decorators.get_remote_user')
	def test_course_sharing_scopes_externalizes(self, mock_container, mock_rem_user):
		class Container(object):
			def __contains__(self, o): return True
		mock_container.is_callable().returns(Container())
		mock_rem_user.is_callable()

		from ..decorators import _SharingScopesAndDiscussionDecorator

		inst = courses.CourseInstance()
		getattr(inst, 'Discussions' ) # this creates the Public scope
		getattr(inst, 'SubInstances')
		ntiid =  'tag:nextthought.com,2011-10:NTI-OID-0x12345'
		inst.SharingScopes['Public'].to_external_ntiid_oid = lambda: ntiid

		subinst = courses.ContentCourseSubInstance()
		inst.SubInstances['sec1'] = subinst
		getattr(subinst, 'Discussions')
		ntiid2 = ntiid + '2'
		subinst.SharingScopes['Public'].to_external_ntiid_oid = lambda: ntiid2

		result = {}
		_SharingScopesAndDiscussionDecorator(subinst, None)._do_decorate_external(subinst, result)

		assert_that( result, has_entry( 'SharingScopes',
										has_entries( 'Class', 'CourseInstanceSharingScopes',
													 'Items', has_entries(
														 'Public', has_entries('Creator', 'system',
																			   'Class', 'Community', # Really CourseInstanceSharingScope
																			   'MimeType', 'application/vnd.nextthought.community',
																			   'NTIID', ntiid2,
																			   'ID', ntiid2,
																			   'Username', ntiid2))) ) )
		assert_that( result, has_entry( 'ParentSharingScopes',
										has_entries('Class', 'CourseInstanceSharingScopes',
													'Items', has_entry(
														'Public', has_entries('Creator', 'system',
																			  'NTIID', ntiid,
																			  'ID', ntiid,
																			  'Username', ntiid))) ) )

		assert_that( result, has_entry('ParentDiscussions',
									   has_entries('Creator', ntiid)))

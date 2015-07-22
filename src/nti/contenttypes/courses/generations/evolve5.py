#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 5

from zope import component
from zope.component.hooks import site as current_site

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from ..interfaces import ICourseCatalog
from ..interfaces import ICourseInstance
from ..interfaces import INonPublicCourseInstance

FOR_CREDIT_FORUM_KEYS = ('In_Class_Announcements', 'In_Class_Discussions')

def do_evolve(context, generation=generation):

	conn = context.connection
	dataserver_folder = conn.root()['nti.dataserver']

	sites = dataserver_folder['++etc++hostsites']
	for site in sites.values():
		with current_site(site):
			course_catalog = component.getUtility(ICourseCatalog)
			for entry in course_catalog.iterCatalogEntries():
				course = ICourseInstance(entry, None)

				# Only public courses with auto-created topics
				if 		not course \
					or 	INonPublicCourseInstance.providedBy( course ) \
					or 	not ICourseDiscussions( course, None ):
					continue

				board = course.Discussions
				for_credit_scope = course.SharingScopes.get( 'ForCredit' )
				public_scope = course.SharingScopes.get( 'Public' )

				# Look for for-credit forums with incorrect creators.
				for in_class_key in FOR_CREDIT_FORUM_KEYS:
					forum = board.get( in_class_key )
					if forum is not None:
						if forum.creator == public_scope:
							logger.info( 'Changing creator for entry (entry=%s) (forum=%s)',
										entry.ntiid, in_class_key )

							forum.sharingTargets
							forum.creator = for_credit_scope
							for topic in forum.values():
								if topic.creator == public_scope:
									logger.info( 'Changing topic creator for entry (entry=%s) (topic=%s)',
												entry.ntiid, topic.__name__ )
									topic.creator = for_credit_scope

	logger.info('contenttypes.courses evolution %s done',
				generation)


def evolve(context):
	"""
	Find content-created discussions scoped to Public instead of ForCredit.
	"""
	do_evolve(context, generation)

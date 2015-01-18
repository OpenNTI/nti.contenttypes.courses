#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Forum objects related to courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from . import MessageFactory as _

from zope import interface
from zope.cachedescriptors.property import cachedIn

from nti.dataserver.contenttypes.forums.board import CommunityBoard
from nti.dataserver.contenttypes.forums.forum import CommunityForum

from nti.externalization.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import TYPE_OID

from .interfaces import ICourseInstanceBoard

@interface.implementer(ICourseInstanceBoard)
class CourseInstanceBoard(CommunityBoard):
	"""
	The board for a course.
	"""

	# The iPad isn't ready to have this appear externally as something different
	# mime_type = mimeType = 'application/vnd.nextthought.courses.courseinstanceboard'

	__external_class_name__ = 'CommunityBoard'

	# Override things related to ntiids.
	# These don't have global names, so they must be referenced
	# by OID
	NTIID_TYPE = _ntiid_type = TYPE_OID
	NTIID = cachedIn('_v_ntiid')(to_external_ntiid_oid)

	def createDefaultForum(self):
		if CommunityForum.__default_name__ in self:
			return self[CommunityForum.__default_name__]

		forum = CommunityForum()
		forum.creator = self.creator
		self[forum.__default_name__] = forum
		forum.title = _('Forum')

		return forum

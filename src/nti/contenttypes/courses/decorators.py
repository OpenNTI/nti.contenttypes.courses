#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.externalization.singleton import SingletonDecorator

@component.adapter(ICourseOutlineNode)
@interface.implementer(IExternalObjectDecorator)
class _CourseOutlineNodeDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		if not original.LessonOverviewNTIID:
			external.pop('LessonOverviewNTIID', None)
		if 'ntiid' not in external and getattr(original, 'ntiid', None):
			external['ntiid'] = original.ntiid

@component.adapter(IJoinCourseInvitation)
@interface.implementer(IExternalObjectDecorator)
class _JoinCourseInvitationDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		external.pop(StandardExternalFields.CREATED_TIME, None)
		external.pop(StandardExternalFields.LAST_MODIFIED, None)

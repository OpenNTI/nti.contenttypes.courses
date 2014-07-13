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
from hamcrest import has_entries
from hamcrest import has_item
from hamcrest import same_instance

from nti.testing import base
from nti.testing import matchers

from nti.testing.matchers import verifiably_provides
from nti.testing.matchers import validly_provides
from nti.externalization.tests import externalizes

from .. import outlines
from .. import courses
from .. import interfaces

from datetime import datetime

from . import CourseLayerTest

class TestCourseOutline(CourseLayerTest):

	set_up_packages = (__name__,)

	def test_outline_implements(self):
		assert_that( outlines.CourseOutlineNode(), verifiably_provides(interfaces.ICourseOutlineNode) )
		assert_that( outlines.CourseOutline(), verifiably_provides(interfaces.ICourseOutline) )

	def test_outline_containment(self):
		inst = courses.CourseInstance()
		outline = inst.Outline
		node = outlines.CourseOutlineNode()
		outline.append(node)
		node2 = outlines.CourseOutlineContentNode(ContentNTIID='tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.lec:01_LESSON',
												  AvailableBeginning=datetime.now() )
		node.append(node2)

		assert_that( node, validly_provides(interfaces.ICourseOutlineNode ))
		assert_that( outline, validly_provides(interfaces.ICourseOutline ))
		assert_that( inst, validly_provides(interfaces.ICourseInstance ))

	def test_outline_externalizes(self):

		inst = courses.CourseInstance()
		outline = inst.Outline
		node = outlines.CourseOutlineNode()
		outline.append(node)
		outline.src = 'src/is/this'
		node2 = outlines.CourseOutlineContentNode(	ContentNTIID='tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.lec:01_LESSON',
												 	AvailableBeginning=datetime.now() )
		outline.append(node2)

		assert_that( inst, externalizes(has_entries('Class', 'CourseInstance',
													'Outline', has_entries( #'Links', has_item(has_entry('rel', 'Contents')), # A higher level will provide access to contents
																			'src', 'src/is/this',
																		   	'MimeType', 'application/vnd.nextthought.courses.courseoutline'),
													'MimeType', 'application/vnd.nextthought.courses.courseinstance')) )

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Traversal related objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.location.interfaces import LocationError

from pyramid.traversal import find_interface
from pyramid.interfaces import IRequest

from zope.traversing.interfaces import ITraversable
from zope.traversing.interfaces import IPathAdapter

from nti.app.products.courseware.interfaces import ICoursePagesContainerResource

from nti.appserver import interfaces

from nti.appserver._dataserver_pyramid_traversal import _AbstractPageContainerResource
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import ContainerAdapterTraversable

@interface.implementer(ICoursePagesContainerResource)
class _CoursePageContainerResource(_AbstractPageContainerResource):
	"""
	A leaf on the traversal tree. Exists to be a named thing that
	we can match view names with. Should be followed by the view name.
	"""

@interface.implementer(ITraversable)
@component.adapter(ICourseInstance, IRequest)
class CoursePagesTraversable(ContainerAdapterTraversable):
	#TODO: Update this comment
	"""	
	Looks for a key in the form Pages(NTIID)/view_name, as a special
	case. Otherwise, looks for named views, or named path adapters if
	no key exists.
	"""

	def traverse(self, key, remaining_path):
		
		# First, try to figure out if our key is in 
		# the form, /Pages(<ntiid>). 

		pfx = 'Pages('
		if key.startswith(pfx) and  key.endswith(')'):
			key = key[len(pfx):-1]
			resource = _CoursePageContainerResource(self, self.request, name=key, parent=self.context)
			if not resource:
				raise LocationError
			return resource
	
		# Otherwise, we look for a named path adapter. 
		return super(CoursePagesTraversable, self).traverse(key, remaining_path)

@interface.implementer(IPathAdapter)
def CourseCatalogEntryTraverser(instance, request):
	"""
	Courses can be traversed to their catalog entry.
	"""
	return ICourseCatalogEntry(instance)


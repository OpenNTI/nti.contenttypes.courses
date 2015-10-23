#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parsing an outline.

This module is private because the outline definition is not
formally defined. Instead, see :mod:`nti.contentrendering.plastexpackages.courses`

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

from .outlines import CourseOutlineNode
from .outlines import CourseOutlineContentNode
from .outlines import CourseOutlineCalendarNode

from .interfaces import NTI_COURSE_OUTLINE_NODE

from .interfaces import iface_of_node

from .interfaces import ICourseOutline
from .interfaces import ICourseInstance
from .interfaces import ICourseCatalogEntry

# too many branches
# pylint:disable=I0011,R0912

def _get_catalog_entry(outline):
	course = find_interface(outline, ICourseInstance, strict=False)
	result = ICourseCatalogEntry(course, None)
	return result

def _outline_nodes(outline):
	result = []
	def _recur(node):
		if 	not ICourseOutline.providedBy(node) and \
			getattr(node, 'ntiid', None):
			result.append(node)

		# parse children
		for child in node.values():
			_recur(child)

	_recur(outline)
	return result

def _unregister_nodes(outline):
	registry = component.getSiteManager()
	for node in _outline_nodes(outline):
		unregisterUtility(registry,
						  name=node.ntiid,
						  provided=iface_of_node(node))

def _register_nodes(outline):
	registry = component.getSiteManager()
	for node in _outline_nodes(outline):
		registerUtility(registry,
						component=node,
					    name=node.ntiid,
					    provided=iface_of_node(node))
	
def _attr_val(node, name):
	# Under Py2, lxml will produce byte strings if it is
	# ascii text, otherwise it will already decode it
	# to using utf-8. Because decoding a unicode object first
	# *encodes* it to bytes (using the default encoding, often ascii),
	# exotic chars would throw a UnicodeEncodeError...so watch for that
	# https://mailman-mail5.webfaction.com/pipermail/lxml/2011-December/006239.html
	val = node.get(bytes(name))
	return val.decode('utf-8') if isinstance(val, bytes) else val
	
def _set_unit_ntiid(outline, node, unit, idx):
	entry = _get_catalog_entry(outline)
	base = entry.ntiid if entry is not None else None
	if base:
		provider = get_provider(base) or 'NTI'
		specific = get_specific(base) + ".%s" % idx
		ntiid = make_ntiid(	nttype=NTI_COURSE_OUTLINE_NODE, 
							base=base,
							provider=provider,
							specific=specific)
	else:
		ntiid = _attr_val(unit, str('ntiid'))
	node.ntiid = ntiid

def _set_lesson_ntiid(parent, node, lesson, idx):
	base = parent.ntiid
	provider = get_provider(base) or 'NTI'
	specific = get_specific(base) + ".%s" % idx
	ntiid = make_ntiid(nttype=NTI_COURSE_OUTLINE_NODE,
					   base=base, 
					   provider=provider,
					   specific=specific)
	node.ntiid = ntiid
	
def fill_outline_from_node(outline, course_element):
	"""
	Given a CourseOutline object and an eTree element object containing its
	``unit`` and ``lesson`` definitions,
	fill in the outline. All existing children of the outline are
	removed.

	The caller is responsible for locating the outline node
	(giving it a name and parent). The caller is also responsible
	for matching any timestamp metadata as appropriate (e.g., lastModified),
	as the timestamps will be modified by this function.

	:return: The outline node.
	"""

	_unregister_nodes(outline)
	outline.reset()
	library = component.queryUtility(IContentPackageLibrary)

	def _handle_node(parent_lxml, parent_node):
		for idx, lesson in enumerate(parent_lxml.iterchildren(tag='lesson')):
			node_factory = CourseOutlineContentNode
			# We want to begin divorcing the syllabus/structure of a course
			# from the content that is available. We currently do this
			# by stubbing out the content, and setting flags to be extracted
			# to the ToC so that we don't give the UI back the NTIID.
			if lesson.get(bytes('isOutlineStubOnly')) == 'true':
				# We query for the node factory we use to "hide"
				# content from the UI so that we can enable/disable
				# hiding in certain site policies.
				# (TODO: Be sure this works as expected with the caching)
				node_factory = component.queryUtility(component.IFactory,
													  name='course outline stub node',  # not valid Class or MimeType value
													  default=CourseOutlineCalendarNode)

			lesson_node = node_factory()
			topic_ntiid = _attr_val(lesson, 'topic-ntiid')

			__traceback_info__ = topic_ntiid

			# Now give it the title and description of the content node,
			# if they have them (they may not, but we require them, even if blank).
			# If the XML itself has a value, that overrides

			content_units = library.pathToNTIID(topic_ntiid, skip_cache=True) if library else None
			if not content_units:
				logger.warn("Unable to find referenced course node %s", topic_ntiid)
				content_unit = None
			else:
				content_unit = content_units[-1]

			for attr in 'title', 'description':
				val = _attr_val(lesson, attr) or getattr(content_unit, attr, None)
				if val:
					setattr(lesson_node, attr, val)

			# Now, if our node is supposed to have the NTIID, expose it.
			# Even if it doesn't (and won't be in the schema and won't be
			# externalized) go ahead and put it there for convenience.
			# See the ICourseOutlineCalendarNode for information.
			if topic_ntiid:
				lesson_node.ContentNTIID = topic_ntiid

			lesson_node.src = _attr_val(lesson, str('src'))
			_set_lesson_ntiid(parent_node, lesson_node, lesson, idx)

			parent_node.append(lesson_node)
			# Sigh. It looks like date is optionally a comma-separated
			# list of datetimes. If there is only one, that looks like
			# the end date, not the beginning date.
			dates = lesson.get('date', ())
			if dates:
				dates = dates.split(',')
			if len(dates) == 1:
				lesson_node.AvailableEnding = dates[0]
			elif len(dates) == 2:
				lesson_node.AvailableBeginning = dates[0]
				lesson_node.AvailableEnding = dates[1]
			_handle_node(lesson, lesson_node)

	for idx, unit in enumerate(course_element.iterchildren(tag='unit')):
		unit_node = CourseOutlineNode()
		unit_node.title = _attr_val(unit, str('label'))
		unit_node.src = _attr_val(unit, str('src'))
		_set_unit_ntiid(outline, unit_node, unit, idx)
		outline.append(unit_node)
		_handle_node(unit, unit_node)

	_register_nodes(outline)
	return outline

def fill_outline_from_key(outline, key, xml_parent_name=None, force=False):
	"""
	Given a course outline node and a :class:`.IDelimitedHierarchyKey`,
	read the XML from the key's contents
	and use :func:`fill_outline_from_node` to populate the outline.

	Unlike that function, this function does set the last modified time
	to the time of that key. It also only does anything if the modified time
	has changed.

	:keyword xml_parent_name: If given, then we will first seek to the first
		occurrence of an element with this name in the DOM and fill from
		than node rather than filling from the root.


	:return: The outline node.
	"""

	if not force and key.lastModified <= outline.lastModified:
		return False

	__traceback_info__ = key, outline
	node = key.readContentsAsETree()
	if xml_parent_name:
		try:
			node = next(node.iterchildren(tag=xml_parent_name))
		except StopIteration:
			raise ValueError("No outline child in key", key, xml_parent_name)
	fill_outline_from_node(outline, node)

	outline.lastModified = key.lastModified
	return True

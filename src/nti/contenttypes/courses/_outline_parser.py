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

from nti.coremetadata.interfaces import IRecordable

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific

from nti.recorder.record import copy_records
from nti.recorder.record import get_transactions
from nti.recorder.record import remove_transaction_history

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
		# XXX: Check ntiid attribute in case of global courses
		if not ICourseOutline.providedBy(node) and getattr(node, 'ntiid', None):
			result.append(node)

		# parse children
		for child in node.values():
			_recur(child)

	_recur(outline)
	return result
outline_nodes = _outline_nodes

def _is_node_locked(node):
	return IRecordable.providedBy(node) and node.locked

def _is_node_move_locked(children):
	return any((_is_node_locked(x) for x in children))

def _can_be_removed(registered, force=False):
	result = registered is not None and \
			 (force or not _is_node_locked(registered))
	return result
can_be_removed = _can_be_removed

def _get_removed_nodes(outline, registry=None, force=False):
	removed = []
	registry = component.getSiteManager() if registry is None else registry
	for node in _outline_nodes(outline):
		if _can_be_removed(node, force=force):
			removed.append(node)
	return removed

def _unregister_nodes(outline, registry=None, force=False):
	removed_nodes = _get_removed_nodes(outline, registry, force)
	for removed in removed_nodes:
		unregisterUtility(registry,
 						  name=removed.ntiid,
 					 	  provided=iface_of_node(removed))
	return removed
unregister_nodes = _unregister_nodes

def _get_node(node_ntiid, obj, registry=None):
	registry = component.getSiteManager() if registry is None else registry
	result = registry.queryUtility(iface_of_node(obj), name=node_ntiid)
	return result
get_node = _get_node

def _register_nodes(outline, registry=None, publish=False):
	registry = component.getSiteManager() if registry is None else registry
	for node in _outline_nodes(outline):
		if _get_node(node.ntiid, node) is None:
			registerUtility(registry,
							component=node,
							name=node.ntiid,
							provided=iface_of_node(node))
		if publish:
			node.publish()
register_nodes = _register_nodes

def _copy_remove_transactions(removed_nodes, record_map, registry=None):
	registry = component.getSiteManager() if registry is None else registry
	for node_ntiid, node in removed_nodes.items():
		provided = iface_of_node(node)
		new_node = registry.queryUtility(provided, name=node_ntiid)
		if new_node is None:
			remove_transaction_history(node)
		else:
			records = record_map.get(node_ntiid) or ()
			copy_records(new_node, records)

def _attr_val(node, name):
	# Under Py2, lxml will produce byte strings if it is
	# ascii text, otherwise it will already decode it
	# to using utf-8. Because decoding a unicode object first
	# *encodes* it to bytes (using the default encoding, often ascii),
	# exotic chars would throw a UnicodeEncodeError...so watch for that
	# https://mailman-mail5.webfaction.com/pipermail/lxml/2011-December/006239.html
	val = node.get(bytes(name))
	return val.decode('utf-8') if isinstance(val, bytes) else val

def _get_unit_ntiid(outline, unit, idx):
	entry = _get_catalog_entry(outline)
	base = entry.ntiid if entry is not None else None
	if base:
		provider = get_provider(base) or 'NTI'
		specific = get_specific(base) + ".%s" % idx
		ntiid = make_ntiid(nttype=NTI_COURSE_OUTLINE_NODE,
						   base=base,
						   provider=provider,
						   specific=specific)
	else:
		ntiid = _attr_val(unit, str('ntiid'))
	return ntiid

def _get_lesson_ntiid(parent, idx):
	"""
	Build an ntiid for the current node.
	"""
	base = parent.ntiid
	provider = get_provider(base) or 'NTI'
	specific_base = get_specific(base)
	specific = specific_base + ".%s" % idx
	ntiid = make_ntiid(nttype=NTI_COURSE_OUTLINE_NODE,
					   base=base,
					   provider=provider,
					   specific=specific)
	return ntiid

def _publish( node ):
	try:
		node.publish()
	except AttributeError:
		pass

def _build_outline_node(node_factory, lesson, lesson_ntiid, library):
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
	lesson_node.ntiid = lesson_ntiid

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
	_publish( lesson_node )
	return lesson_node

def _update_parent_children(parent_node, old_children, transactions):
	"""
	If there are old_children and the parent node is `move`
	locked, we must preserve the existing order state.

	We currently do not support (*only*) user-deleted nodes (without
	some additional state management or placeholders). We do not
	support sync inserts when there are user-locked objects in play.
	"""
	if old_children and _is_node_move_locked(old_children):
		new_children = list(parent_node.values())
		new_child_map = {x.ntiid:x for x in new_children}
		# Our children may already have their transactions recorded,
		# make sure we don't clear them via wipe.
		parent_node.clear( event=False )
		for i, old_child in enumerate(old_children):
			try:
				new_child = new_children[i]
			except IndexError:
				new_child = None
			if new_child and old_child.ntiid != new_child.ntiid:
				# TODO Event?
				logger.info('Found moved node on sync (old=%s) (new=%s)',
							old_child.ntiid, new_child.ntiid)

			new_child = new_child_map.get(old_child.ntiid)
			if new_child is None and _is_node_locked(old_child):
				# Preserve our locked child from deletion.
				new_child = old_child

			if new_child is not None:
				parent_node.append(new_child)
				copy_records(new_child, transactions.get( old_child.ntiid, () ))

def _get_node_factory(lesson):
	result = CourseOutlineContentNode
	# We want to begin divorcing the syllabus/structure of a course
	# from the content that is available. We currently do this
	# by stubbing out the content, and setting flags to be extracted
	# to the ToC so that we don't give the UI back the NTIID.
	if lesson.get(bytes('isOutlineStubOnly')) == 'true':
		# We query for the node factory we use to "hide"
		# content from the UI so that we can enable/disable
		# hiding in certain site policies.
		# (TODO: Be sure this works as expected with the caching)
		ivalid_name = 'course outline stub node'  # not valid Class or MimeType value
		result = component.queryUtility(component.IFactory,
										name=ivalid_name,
										default=CourseOutlineCalendarNode)
	return result

def _handle_node(parent_lxml, parent_node, library, removed_nodes, transactions):
	"""
	Recursively fill in outline nodes and their children.
	"""
	old_children = list(parent_node.values())
	parent_node.clear( event=False )

	for idx, lesson in enumerate(parent_lxml.iterchildren(tag='lesson')):
		node_factory = _get_node_factory(lesson)
		# We may re-use ntiids of user-created nodes here, which is ok
		# since we do not allow the insertion of new-nodes once user
		# locked nodes exist.
		lesson_ntiid = _get_lesson_ntiid(parent_node, idx)
		lesson_node = node_factory()
		old_node = _get_node(lesson_ntiid, lesson_node)

		if lesson_ntiid not in removed_nodes and old_node is not None:
			if _is_node_locked(old_node):
				logger.info('Lesson node not syncing due to sync lock (%s)', lesson_ntiid)
			lesson_node = old_node
		else:
			lesson_node = _build_outline_node(node_factory, lesson,
											  lesson_ntiid, library)

		# Must add to our parent_node now to avoid NotYet exceptions.
		parent_node.append(lesson_node)
		_handle_node(lesson, lesson_node, library, removed_nodes, transactions)

	_update_parent_children( parent_node, old_children, transactions )

def fill_outline_from_node(outline, course_element, force=False):
	"""
	Given a CourseOutline object and an eTree element object containing its
	``unit`` and ``lesson`` definitions,
	fill in the outline. All existing children of the outline are
	removed, if not locked.

	The caller is responsible for locating the outline node
	(giving it a name and parent). The caller is also responsible
	for matching any timestamp metadata as appropriate (e.g., lastModified),
	as the timestamps will be modified by this function.

	:return: The outline node.
	"""
	# Capture our transactions early since clear may remove them.
	transactions = {node.ntiid:get_transactions(node) for node in _outline_nodes(outline)}
	removed_nodes = {x.ntiid:x for x in _get_removed_nodes(outline, force=force)}
	library = component.queryUtility(IContentPackageLibrary)
	old_children = list(outline.values())
	outline.clear( event=False )

	for idx, unit in enumerate(course_element.iterchildren(tag='unit')):
		unit_ntiid = _get_unit_ntiid(outline, unit, idx)
		unit_node = CourseOutlineNode()
		old_node = _get_node(unit_ntiid, unit_node)
		if unit_ntiid not in removed_nodes and old_node is not None:
			if _is_node_locked(old_node):
				logger.info('Unit node not syncing due to sync lock (%s)', unit_ntiid)
			unit_node = old_node
		else:
			unit_node.title = _attr_val(unit, str('label'))
			unit_node.src = _attr_val(unit, str('src'))
			unit_node.ntiid = unit_ntiid
			_publish( unit_node )

		outline.append( unit_node )
		_handle_node(unit, unit_node, library, removed_nodes, transactions)
	_update_parent_children( outline, old_children, transactions )

	# Unregister removed and re-register
	registry = component.getSiteManager()
	for removed_ntiid, removed_node in removed_nodes.items():
		unregisterUtility(registry,
 						  name=removed_ntiid,
 						  provided=iface_of_node(removed_node))
	_register_nodes(outline, publish=True)

	# After registering, restore tx history
	# TODO Do we need this anymore?
	_copy_remove_transactions(removed_nodes, transactions)

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
	fill_outline_from_node(outline, node, force=force)

	outline.lastModified = key.lastModified
	return True

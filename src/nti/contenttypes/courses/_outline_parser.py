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

from nti.contentlibrary import ContentRemovalException

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode
from nti.contenttypes.courses.interfaces import ICourseOutlineCalendarNode

from nti.contenttypes.courses.interfaces import NTI_COURSE_OUTLINE_NODE

from nti.contenttypes.courses.outlines import CourseOutlineNode
from nti.contenttypes.courses.outlines import CourseOutlineContentNode

from nti.coremetadata.interfaces import IRecordable

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import copy_records
from nti.recorder.record import get_transactions
from nti.recorder.record import remove_transaction_history

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

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

def _is_locked( obj ):
	return IRecordable.providedBy(obj) and obj.isLocked()

def _is_node_locked(node):
	result = _is_locked( node )
	if not result:
		# Check lesson to make sure we do not remove a node
		# that may have an edited lesson.
		lesson = node.LessonOverviewNTIID
		if lesson:
			lesson = find_object_with_ntiid( lesson )
			result = _is_locked( lesson )
	return result

def _is_node_move_locked(container, children):
	# Ideally, the child_order_locked field alone will indicate locked,
	# but fall back to child status if necessary.
	return getattr(container, 'child_order_locked', False) \
		or any((_is_node_locked(x) for x in children))

def _can_be_removed(registered, force=False):
	result = registered is not None and (force or not _is_node_locked(registered))
	return result
can_be_removed = _can_be_removed

def _get_nodes_to_remove(outline, force=False):
	removed = []
	for node in _outline_nodes(outline):
		if _can_be_removed(node, force=force):
			removed.append(node)
	return removed

def _do_unregister( removed_node, registry=None ):
	iface_to_remove = (iface_of_node( removed_node ),)
	if ICourseOutlineContentNode.providedBy( removed_node ):
		iface_to_remove = ( ICourseOutlineCalendarNode, ICourseOutlineContentNode )
	result = False
	for iface in iface_to_remove:
		result = unregisterUtility(registry,
						  		   name=removed_node.ntiid,
						  		   provided=iface)
	return result

def _unregister_nodes(outline, registry=None, force=False):
	result = []
	nodes = _get_nodes_to_remove(outline, force)
	for node in nodes:
		if _do_unregister( node, registry=registry ):
			result.append(node)
	return result
unregister_nodes = _unregister_nodes

def _get_node(node_ntiid, obj, registry=None):
	registry = component.getSiteManager() if registry is None else registry
	result = registry.queryUtility(iface_of_node(obj), name=node_ntiid)
	return result
get_node = _get_node

def _register_nodes(outline, registry=None):
	registry = component.getSiteManager() if registry is None else registry
	for node in _outline_nodes(outline):
		if _get_node(node.ntiid, node, registry=registry) is None:
			registerUtility(registry,
							component=node,
							name=node.ntiid,
							provided=iface_of_node(node))
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

def _publish(node):
	try:
		node.publish(event=False)
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
		# XXX: Might be common if lessons are stored under bundle.
		logger.warn("Unable to find referenced course node %s", topic_ntiid)
		content_unit = None
	else:
		content_unit = content_units[-1]

	# Use either title or label for lesson titles.
	for attr in 'title', 'label':
		val = _attr_val(lesson, attr) or getattr(content_unit, attr, None)
		if val:
			setattr(lesson_node, str('title'), val)
			break

	desc_val = _attr_val(lesson, 'description') \
			or getattr(content_unit, 'description', None)
	if desc_val:
		setattr(lesson_node, str('description'), desc_val)

	# Now, if our node is supposed to have the NTIID, expose it.
	# Even if it doesn't (and won't be in the schema and won't be
	# externalized) go ahead and put it there for convenience.
	# See the ICourseOutlineCalendarNode for information.
	if topic_ntiid:
		lesson_node.ContentNTIID = topic_ntiid

	# For the legacy calendar nodes, we now create content nodes
	# that we guarantee has no src.
	if not _is_outline_stub(lesson):
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
	_publish(lesson_node)
	return lesson_node

def _update_parent_children(parent_node, old_children, transactions, force=False):
	"""
	If there are old_children and the parent node is `move`
	locked, we must preserve the existing order state. We do not
	support sync inserts when there are user-locked objects in play.
	"""
	new_children = list(parent_node.values())
	new_child_map = {x.ntiid:x for x in new_children}
	if old_children and _is_node_move_locked(parent_node, old_children):
		# Our children may already have their transactions recorded,
		# make sure we don't clear them via wipe.
		parent_node.clear(event=False)
		for i, old_child in enumerate(old_children):
			try:
				new_child = new_children[i]
			except IndexError:
				new_child = None
			if 		new_child is not None \
				and old_child.ntiid != new_child.ntiid:
				# TODO: Event?
				logger.info('Found moved node on sync (old=%s) (new=%s)',
							old_child.ntiid, new_child.ntiid)

			new_child = new_child_map.get(old_child.ntiid)
			if new_child is None and _is_node_locked(old_child):
				# Preserve our locked child from deletion.
				new_child = old_child

			if new_child is not None:
				parent_node.append(new_child)
				copy_records(new_child, transactions.get(old_child.ntiid, ()))

		# Possibly sync-appended items that we are ignoring...
		ignored_children = set(new_child_map.keys()) - set((x.ntiid for x in old_children))
		for ignored_child in ignored_children:
			# TODO: Event
			logger.info('Not appending new node (%s) since parent node (%s) has sync locked children',
						ignored_child,
						getattr(parent_node, 'ntiid', 'Outline'))
	elif	old_children \
		and len( old_children ) > len( new_child_map ):
		# Our parent node may be losing children, including those with API
		# created data underneath. We allow it only if none of those
		# underlying elements are locked (or we have a force flag).
		def _check_locked( node ):
			for child in node.values():
				if _is_node_locked( child ):
					msg = 'Force removing user edited node during sync (node=%s) (parent=%s)' % \
						  (child.ntiid, getattr(parent_node, 'ntiid', 'Outline'))
					if not force:
						raise ContentRemovalException(msg)
					else:
						logger.info(msg)
				_check_locked( child )
		for candidate in old_children:
			try:
				if candidate.ntiid not in new_child_map:
					_check_locked( candidate )
			except AttributeError:
				# Some old courses (F 2014 BIOL), have nodes without ntiids.
				pass

def _is_outline_stub(lesson):
	return lesson.get(bytes('isOutlineStubOnly')) == 'true'

def _use_or_create_node(node_ntiid, new_node, removed_nodes, builder, registry=None):
	"""
	Use an existing node for the given ntiid or return a brand new node,
	and the old children of our node, if they exist.
	"""
	old_children = None
	old_node = _get_node(node_ntiid, new_node, registry=registry)
	if old_node is not None:
		# Capture our old children here for merge.
		old_children = list(old_node.values())
		if node_ntiid not in removed_nodes and _is_node_locked(old_node):
			logger.info('Node not syncing due to sync lock (%s)', node_ntiid)
		elif node_ntiid not in removed_nodes:
			# We have a registered node that is not locked and not removed.
			# This case should really not happen, but in alpha, we've seen nodes
			# with ntiids that do not match their registered ntiids. Clean them up.
			logger.info('Mis-registered node? (register_id=%s) (node_ntiid=%s)',
						node_ntiid,
						getattr(old_node, 'ntiid', ''))
			removed_nodes[ node_ntiid ] = old_node
			old_node = None
		else:
			# Removed node
			old_node = None

	if old_node is not None:
		result = old_node
	else:
		result = builder()
	return result, old_children

def _handle_node(parent_lxml, parent_node, old_children, library,
				 removed_nodes, transactions, force, registry=None):
	"""
	Recursively fill in outline nodes and their children.
	"""
	parent_node.clear(event=False)

	for idx, lesson in enumerate(parent_lxml.iterchildren(tag='lesson')):
		lesson_ntiid = _get_lesson_ntiid(parent_node, idx)
		def builder():
			return _build_outline_node(CourseOutlineContentNode,
									   lesson,
									   lesson_ntiid,
									   library)

		lesson_node, old_lesson_children = _use_or_create_node(lesson_ntiid,
															   CourseOutlineContentNode(),
										  					   removed_nodes,
										  					   builder,
										  					   registry=registry)

		# Must add to our parent_node now to avoid NotYet exceptions.
		parent_node.append(lesson_node)
		_handle_node(lesson, lesson_node, old_lesson_children, library,
					 removed_nodes, transactions, force, registry=registry)

	_update_parent_children(parent_node, old_children, transactions, force)

def fill_outline_from_node(outline, course_element, force=False, registry=None, **kwargs):
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
	library = component.queryUtility(IContentPackageLibrary)
	registry = component.getSiteManager() if registry is None else registry

	# Capture our transactions early since clear may remove them.
	transactions = {node.ntiid:get_transactions(node) for node in _outline_nodes(outline)}

	# Get nodes that can be removed
	removed_nodes = {x.ntiid:x for x in _get_nodes_to_remove(outline, force=force)}

	old_children = tuple(outline.values())
	outline.clear(event=False)

	for idx, unit in enumerate(course_element.iterchildren(tag='unit')):
		unit_ntiid = _get_unit_ntiid(outline, unit, idx)

		def builder():
			new_node = CourseOutlineNode()
			new_node.title = _attr_val(unit, str('label'))
			new_node.src = _attr_val(unit, str('src'))
			new_node.ntiid = unit_ntiid
			_publish(new_node)
			return new_node

		unit_node, old_unit_children = _use_or_create_node(unit_ntiid,
														   CourseOutlineNode(),
														   removed_nodes,
														   builder,
														   registry=registry)

		outline.append(unit_node)
		_handle_node(unit, unit_node, old_unit_children, library,
					 removed_nodes, transactions, force, registry=registry)
	_update_parent_children(outline, old_children, transactions, force)

	# Unregister removed and re-register
	for removed_node in removed_nodes.values():
		_do_unregister( removed_node, registry=registry )
	_register_nodes(outline, registry)

	# After registering, restore tx history
	# TODO: Do we need this anymore?
	_copy_remove_transactions(removed_nodes, transactions, registry=registry)

	return outline

def fill_outline_from_key(outline, key, xml_parent_name=None, force=False,
						  registry=None, **kwargs):
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

	entry = _get_catalog_entry(outline)
	entry_ntiid = getattr( entry, 'ntiid', '' )
	logger.info( 'Updating course outline for %s', entry_ntiid )

	__traceback_info__ = key, outline
	node = key.readContentsAsETree()
	if xml_parent_name:
		try:
			node = next(node.iterchildren(tag=xml_parent_name))
		except StopIteration:
			raise ValueError("No outline child in key", key, xml_parent_name)
	fill_outline_from_node(outline, node, force=force, registry=registry, **kwargs)

	outline.lastModified = key.lastModified
	return True

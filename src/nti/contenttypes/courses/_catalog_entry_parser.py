#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A parser for the on-disk representation
of catalog information.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

import isodate
import pytz
import datetime
from urlparse import urljoin

from .interfaces import INonPublicCourseInstance

from .legacy_catalog import CourseCatalogInstructorLegacyInfo
from .legacy_catalog import CourseCreditLegacyInfo

from nti.dataserver.users import Entity

def _quiet_delattr(o, k):
	try:
		delattr(o, k)
	except AttributeError:
		pass

def fill_entry_from_legacy_json(catalog_entry, info_json_dict, base_href='/'):
	"""
	Given a course catalog entry, fill in the data
	from an old-style ``course_info.json``.

	You are responsible for correct parentage, and you are
	responsible for updating modification times. You are also
	responsible for setting an `ntiid` if needed.

	:keyword str base_href: The relative path at which
		urls should be interpreted.
	"""

	if info_json_dict.get('is_non_public'):
		# This should move somewhere else...,
		# but for nti.app.products.courseware ACL support
		# (when these are not children of a course) it's convenient
		interface.alsoProvides(catalog_entry, INonPublicCourseInstance)

	for field, key in (('Description', 'description'),
					   ('Title', 'title'),
					   ('ProviderUniqueID', 'id'),
					   ('ProviderDepartmentTitle', 'school'),
					   ('ntiid', 'ntiid'),
					   ('Term', 'term'), # XXX: non-interface
					   ('InstructorsSignature', 'InstructorsSignature')):
		val = info_json_dict.get(key)
		__traceback_info__ = field, key, val
		if val:
			setattr( catalog_entry, str(field), val)
		else:
			# XXX: Does deleting fieldproperties do the right thing?
			_quiet_delattr(catalog_entry, str(field))

	if 'startDate' in info_json_dict:
		catalog_entry.StartDate = isodate.parse_datetime(info_json_dict['startDate'])
		# Convert to UTC if needed
		if catalog_entry.StartDate.tzinfo is not None:
			catalog_entry.StartDate = catalog_entry.StartDate.astimezone(pytz.UTC).replace(tzinfo=None)
	else:
		_quiet_delattr(catalog_entry, 'StartDate')

	if 'duration' in info_json_dict:
		# We have durations as strings like "16 weeks"
		duration_number, duration_kind = info_json_dict['duration'].split()
		# Turn those into keywords for timedelta.
		catalog_entry.Duration = datetime.timedelta(**{duration_kind.lower():int(duration_number)})
		# Ensure the end date is derived properly
		assert catalog_entry.StartDate is None or catalog_entry.EndDate
	else:
		_quiet_delattr(catalog_entry, 'Duration')

	# derive preview information if not provided.
	if 'isPreview' in info_json_dict:
		catalog_entry.Preview = info_json_dict['isPreview']
	else:
		_quiet_delattr(catalog_entry, 'Preview')
		if catalog_entry.StartDate and datetime.datetime.utcnow() < catalog_entry.StartDate:
			assert catalog_entry.Preview


	instructors = []
	# For externalizing the photo URLs, we need
	# to make them absolute.
	# TODO: Switch these to DelimitedHierarchyKeys
	if 'instructors' in info_json_dict:
		for inst in info_json_dict['instructors']:
			username = inst.get('username','')
			userid = inst.get('userid','') # e.g legacy OU userid
			# XXX:  The need to map catalog instructors to the actual
			# instructors is going away, coming from a new place
			try:
				if Entity.get_entity(username) is None and Entity.get_entity(userid) is not None:
					username = userid
			except LookupError:
				# no dataserver
				pass

			instructor = CourseCatalogInstructorLegacyInfo( Name=inst['name'],
															JobTitle=inst['title'],
															username=username)
			if inst.get('defaultphoto'):
				photo_name = inst['defaultphoto']
				# Ensure it exists and is readable before we advertise it
				instructor.defaultphoto = urljoin(base_href, photo_name)

			instructors.append( instructor )

		catalog_entry.Instructors = tuple(instructors)
	else:
		_quiet_delattr(catalog_entry, 'Instructors')


	if info_json_dict.get('video'):
		catalog_entry.Video = info_json_dict.get('video').encode('utf-8')
	else:
		_quiet_delattr(catalog_entry, 'Video')
	if 'credit' in info_json_dict:
		catalog_entry.Credit = [CourseCreditLegacyInfo(Hours=d['hours'],Enrollment=d['enrollment'])
								for d in info_json_dict.get('credit', [])]
	else:
		_quiet_delattr(catalog_entry, 'Credit')

	if 'schedule' in info_json_dict:
		catalog_entry.Schedule = info_json_dict.get('schedule', {})
	else:
		_quiet_delattr(catalog_entry, 'Schedule')

	if 'prerequisites' in info_json_dict:
		catalog_entry.Prerequisites = info_json_dict.get('prerequisites', [])
	else:
		_quiet_delattr(catalog_entry, 'Prerequisites')


	return catalog_entry


def fill_entry_from_legacy_key(catalog_entry, key, base_href='/'):
	"""
	Given a course catalog entry and a :class:`.IDelimitedHierarchyKey`,
	read the JSON from the key's contents
	and use :func:`fill_entry_from_legacy_json` to populate the entry.

	Unlike that function, this function does set the last modified
	time to the time of that key (and sets the root of the catalog entry to
	the key). It also only does anything if the modified time has
	changed.

	:return: The entry
	"""

	if key.lastModified <= catalog_entry.lastModified:
		return catalog_entry

	json = key.readContentsAsJson()
	fill_entry_from_legacy_json(catalog_entry, json, base_href=base_href)
	catalog_entry.root = key.__parent__
	catalog_entry.key = key
	catalog_entry.lastModified = key.lastModified

	return catalog_entry

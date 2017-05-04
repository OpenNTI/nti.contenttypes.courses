#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A parser for the on-disk representation of catalog information.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urlparse import urljoin
from datetime import datetime
from collections import Mapping

from nti.contentlibrary.dublincore import read_dublincore_from_named_key

from nti.contenttypes.courses.internalization import legacy_to_schema_transform

from nti.externalization.internalization import update_from_external_object

from nti.dataserver.users import Entity


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
    # input check
    additionalProperties = info_json_dict.get('additionalProperties')
    if additionalProperties is not None:
        assert isinstance(additionalProperties, Mapping), \
            "Invalid additionalProperties entry"

    info_json_dict['MimeType'] = catalog_entry.mimeType
    legacy_to_schema_transform(info_json_dict, catalog_entry, delete=True)
    update_from_external_object(catalog_entry, info_json_dict, notify=False)

    # check preview information
    if catalog_entry.StartDate and datetime.utcnow() < catalog_entry.StartDate:
        if not catalog_entry.Preview:
            logger.info('Enabling catalog entry preview flag based on dates')
            catalog_entry.Preview = True

    # check instructors
    if catalog_entry.Instructors:
        instructors = []
        for instructor in catalog_entry.Instructors:
            username = instructor.username or u''
            userid = instructor.userid or u''  # OU legacy
            # XXX: The need to map catalog instructors to the actual
            # instructors is going away, coming from a new place
            try:
                if      Entity.get_entity(username) is None \
                    and Entity.get_entity(userid) is not None:
                    instructor.username = userid
            except LookupError:
                # no dataserver
                pass

            if instructor.defaultphoto:
                # Ensure it exists and is readable before we advertise it
                instructor.defaultphoto = urljoin(base_href,
                                                  instructor.defaultphoto)

            instructors.append(instructor)
        catalog_entry.Instructors = tuple(instructors)

    return catalog_entry


def fill_entry_from_legacy_key(catalog_entry, key, base_href='/', force=False):
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

    if force or key.lastModified > catalog_entry.lastModified:
        __traceback_info__ = key, catalog_entry
        logger.info("Updating catalog entry %s with [legacy] json %s. (dates: key=%s, ce=%s)",
                    catalog_entry.ntiid,
                    key,
                    key.lastModified,
                    catalog_entry.lastModified)

        json = key.readContentsAsYaml()
        fill_entry_from_legacy_json(catalog_entry, json, base_href=base_href)
        catalog_entry.key = key
        catalog_entry.root = key.__parent__
        catalog_entry.lastModified = key.lastModified
        return True
    else:
        logger.info("Skipping catalog entry %s update. (dates: key=%s, ce=%s)",
                    catalog_entry.ntiid,
                    key.lastModified,
                    catalog_entry.lastModified)
    return False


def update_entry_from_legacy_key(entry, key, bucket, base_href='/', force=False):
    modified = fill_entry_from_legacy_key(entry,
                                          key,
                                          force=force,
                                          base_href=base_href)

    # The catalog entry gets the default dublincore info
    # file; for the bundle, we use a different name
    if read_dublincore_from_named_key(entry, bucket, force=force) is not None:
        modified = True

    if not getattr(entry, 'root', None):
        entry.root = bucket
        modified = True

    return modified

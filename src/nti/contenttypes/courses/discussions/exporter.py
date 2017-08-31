#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE

from nti.contenttypes.courses.discussions.parser import path_to_discussions

from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_MAP

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_enrollment_in_hierarchy
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver.users.users import User

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.namedfile.file import safe_filename

from nti.traversal.traversal import find_interface

CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE


def user_topic_file_name(topic):
    headline = topic.headline
    intids = component.queryUtility(IIntIds)
    if intids is not None:
        doc_id = intids.queryId(topic)
        doc_id = str(doc_id) if doc_id is not None else None
    else:
        doc_id = headline.title
    return safe_filename(doc_id or headline.title) + '.json'


def user_topic_dicussion_id(topic):
    name = user_topic_file_name(topic)
    course = find_interface(topic, ICourseInstance, strict=False)
    path = path_to_discussions(course)
    return "%s://%s/%s" % (NTI_COURSE_BUNDLE, path, name)


def export_user_topic_as_discussion(topic):
    course = find_interface(topic, ICourseInstance, strict=False)
    creator = getattr(topic.creator, 'username', topic.creator) or ''
    result = {
        'tags': topic.tags,
        CLASS: "Discussion",
        MIMETYPE: "application/vnd.nextthought.courses.discussion",
    }
    if creator:
        result['creator'] = creator
    # title and content
    headline = topic.headline
    result['body'] = [
        to_external_object(x) for x in headline.body or ()
    ]
    result['title'] = headline.title
    # scope
    scopes = ["All"]
    if not is_course_instructor_or_editor(creator):
        user = User.get_user(creator)
        if user is not None:
            record = get_enrollment_in_hierarchy(course, user)
            if record is not None:  # user dropped
                term = ENROLLMENT_SCOPE_MAP.get(record.Scope)
                scopes = [record.Scope] + list(getattr(term, 'implies', ()))
    result["scopes"] = scopes
    # give a proper id
    dicussion_id = user_topic_dicussion_id(topic)
    result['id'] = dicussion_id
    return result

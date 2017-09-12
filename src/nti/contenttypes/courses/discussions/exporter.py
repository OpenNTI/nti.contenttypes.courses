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

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_MAP

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_enrollment_in_hierarchy
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.dataserver.users.users import User

from nti.externalization.externalization import toExternalObject

from nti.externalization.interfaces import StandardExternalFields

from nti.namedfile.file import safe_filename

from nti.ntiids.ntiids import hexdigest

from nti.traversal.traversal import find_interface

ID = StandardExternalFields.ID
CLASS = StandardExternalFields.CLASS
CREATOR = StandardExternalFields.CREATOR
MIMETYPE = StandardExternalFields.MIMETYPE


def user_topic_file_name(topic, salt=None):
    headline = topic.headline
    intids = component.queryUtility(IIntIds)
    if intids is not None:
        doc_id = intids.queryId(topic)
        doc_id = str(doc_id) if doc_id is not None else None
    else:
        doc_id = headline.title
    result = safe_filename(doc_id or headline.title[:20])
    if salt:
        result = hexdigest(result, salt)
    result = result + '.json'
    return result


def user_topic_dicussion_id(topic, salt=None):
    name = user_topic_file_name(topic, salt)
    course = find_interface(topic, ICourseInstance, strict=False)
    path = path_to_discussions(course)
    return "%s://%s/%s" % (NTI_COURSE_BUNDLE, path, name)


def export_user_topic_as_discussion(topic, salt=None):
    course = find_interface(topic, ICourseInstance, strict=False)
    creator = getattr(topic.creator, 'username', topic.creator) or ''
    result = {
        "icon": None,
        "label": "",
        'tags': topic.tags,
        CLASS: "Discussion",
        MIMETYPE: "application/vnd.nextthought.courses.discussion",
    }
    result[CREATOR] = SYSTEM_USER_ID
    # title and content
    headline = topic.headline
    __traceback_info__ = headline.body
    result['body'] = [
        toExternalObject(x, name='exporter', decorate=False) for x in headline.body or ()
    ]
    result['title'] = headline.title
    # scope
    scopes = [ES_ALL]
    if not is_course_instructor_or_editor(course, creator):
        user = User.get_user(creator)
        if user is not None:
            record = get_enrollment_in_hierarchy(course, user)
            if record is not None:  # user dropped
                term = ENROLLMENT_SCOPE_MAP.get(record.Scope)
                computed = [record.Scope] + list(getattr(term, 'implies', ()))
                if computed != [ES_PUBLIC]:
                    scopes = computed
    result["scopes"] = scopes
    # give a proper id
    dicussion_id = user_topic_dicussion_id(topic, salt)
    result[ID] = dicussion_id
    return result

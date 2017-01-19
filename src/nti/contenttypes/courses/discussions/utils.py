#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from urllib import unquote
from urlparse import urlparse

from zope.security.interfaces import IPrincipal

from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE
from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE_REF

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import SECTIONS
from nti.contenttypes.courses.interfaces import DISCUSSIONS
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_MAP
from nti.contenttypes.courses.interfaces import ENROLLMENT_LINEAGE_MAP

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_user_or_instructor_enrollment_record

from nti.dataserver.interfaces import ACE_ACT_ALLOW

from nti.ntiids.ntiids import make_specific_safe

from nti.traversal.traversal import find_interface

ENROLLED_COURSE_ROOT = ':EnrolledCourseRoot'
ENROLLED_COURSE_SECTION = ':EnrolledCourseSection'


def get_discussion_id(discussion):
    result = getattr(discussion, 'id', discussion)
    return result


def is_nti_course_bundle(discussion):
    iden = get_discussion_id(discussion)
    parts = urlparse(iden) if iden else None
    result = NTI_COURSE_BUNDLE == parts.scheme if parts else False
    return result


def get_discussion_path(discussion):
    iden = get_discussion_id(discussion)
    if is_nti_course_bundle(iden):
        result = iden[len(NTI_COURSE_BUNDLE_REF) - 1:]
        return result
    return None


def get_discussion_key(discussion):
    iden = get_discussion_id(discussion)
    if is_nti_course_bundle(iden):
        parts = urlparse(iden)
        result = os.path.split(unquote(parts.path))
        return result[1]
    return None


def get_discussion_mapped_scopes(discussion):
    result = set()
    for scope in discussion.scopes:
        result.update(ENROLLMENT_LINEAGE_MAP.get(scope) or ())
    return result


def get_course_for_discussion(discussion, context):
    iden = get_discussion_id(discussion)
    if is_nti_course_bundle(iden) and context is not None:
        parent = get_parent_course(context)
        if parent is not None:
            path = get_discussion_path(iden)
            splits = path.split(os.path.sep)
            if SECTIONS in splits:  # e.g. /Sections/02/Discussions
                return parent.SubInstances.get(splits[2]) if len(splits) >= 3 else None
            else:
                return parent
    return None


def get_discussion_for_path(path, context):
    parent = get_parent_course(context)
    path = os.path.sep + \
        path if not path.startswith(os.path.sep) else os.path.sep
    if parent is not None:
        splits = path.split(os.path.sep)
        # e.g. /Sections/02/Discussions/p.json
        if SECTIONS in splits and len(splits) >= 2 and splits[1] == SECTIONS:
            course = parent.SubInstances.get(
                splits[2]) if len(splits) >= 3 else None
            course = None if len(
                splits) < 3 or DISCUSSIONS != splits[3] else course
            name = splits[4] if len(splits) >= 5 else None
        else:
            course = parent  # e.g. /Discussions/p.json
            course = None if len(
                splits) < 2 or DISCUSSIONS != splits[1] else course
            name = splits[2] if len(splits) >= 3 else None

        if course is not None and name:
            discussions = ICourseDiscussions(course, None) or {}
            for prefix in (name, name.replace(' ', '_')):
                result = discussions.get(
                    prefix) or discussions.get(prefix + '.json')
                if result is not None:
                    break
            return result
    return None


def get_topic_key(discussion):
    __traceback_info__ = discussion
    if is_nti_course_bundle(discussion):
        name = get_discussion_path(discussion)
    else:
        name = discussion.title
        if not name:
            name = u''
        elif not isinstance(name, unicode):
            name = name.decode('utf-8', 'ignore')
    name = make_specific_safe(name)
    return name


def get_scope_term(name):
    return ENROLLMENT_SCOPE_MAP.get(name)


def get_implied_by_scopes(scopes=()):
    result = set()
    for scope in scopes or ():
        result.add(scope)
        if scope == ES_ALL:
            result.discard(scope)
            result.update(ENROLLMENT_SCOPE_MAP.keys())
            break
        else:
            es = ENROLLMENT_SCOPE_MAP.get(scope)
            result.update(es.implied_by if es is not None else ())
    return result


def get_forum_scopes(forum):
    result = None
    course = find_interface(forum, ICourseInstance, strict=False)
    m = {v.NTIID: k for k, v in course.SharingScopes.items()} if course else {}
    if hasattr(forum, '__entities__'):
        result = {m[k] for k, v in m.items() if k in forum.__entities__}
    elif hasattr(forum, '__acl__'):
        result = set()
        for ace in forum.__acl__:
            if IPrincipal(ace.actor).id in m and ace.action == ACE_ACT_ALLOW:
                result.add(m[k])
    return result or ()


def resolve_discussion_course_bundle(user, item, context=None, record=None):
    """
    return a tuple of course discussion and preferred topic according the discussion ref
    and user enrollment or None

    :param item: A discussion ref object
    :param context: An object that can be adapted to a course
    :param record: Enrollment record if available
    """

    context = item if context is None else item
    record = get_user_or_instructor_enrollment_record(
        context, user) if record is None else record
    if record is None:
        logger.warn("No enrollment record for user %s under %s", user, context)
        return None

    # enrollment scope. When scope is equals to 'All' it means user is an
    # instructor
    scope = record.Scope

    # get course pointed by the discussion ref
    course = get_course_for_discussion(item, context=record.CourseInstance)
    if course is None:
        logger.warn("No course found for discussion %s", item)
        return None

    # if course is a subinstance, make sure we are enrolled in it and
    # we are not an instructor
    if 		ICourseSubInstance.providedBy(course) \
        and scope != ES_ALL \
        and course != record.CourseInstance:
        return None

    # get course discussion, if needed
    discussion = item
    if not ICourseDiscussion.providedBy(item):
        key = get_discussion_key(item)
        discussion = ICourseDiscussions(course).get(key) if key else None
    scopes = get_implied_by_scopes(
        discussion.scopes) if discussion is not None else ()
    logger.debug("Implied scopes for %s are %s", key, scopes)

    if     	   (not scope) \
            or (not scopes) \
            or (scope != ES_ALL and ES_ALL not in scopes and scope not in scopes):
        logger.warn(
            "User scope %s did not match implied scopes %s", scope, scopes)
        return None
    else:
        topic = None
        topic_key = get_topic_key(discussion)
        topic_title = make_specific_safe(discussion.title)
        m_scope = ES_ALL if scope == ES_ALL \
            else ENROLLMENT_LINEAGE_MAP.get(scope)[0]
        m_scope_term = get_scope_term(m_scope) if m_scope != ES_ALL else None
        m_scope_implies = set(getattr(m_scope_term, 'implies', None) or ())
        for v in course.Discussions.values():
            # check the forum scopes against the mapped enrollment scope
            forum_scopes = get_forum_scopes(v) if m_scope != ES_ALL else ()
            if     m_scope == ES_ALL \
                or m_scope in forum_scopes \
                or m_scope_implies.intersection(forum_scopes):
                if topic_key in v:
                    topic = v[topic_key]
                    break
                elif topic_title in v:
                    topic = v[topic_title]
                    break
        if topic is not None:
            return (discussion, topic)
        return None

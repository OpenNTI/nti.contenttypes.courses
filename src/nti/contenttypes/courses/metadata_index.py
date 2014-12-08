#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.intid

from zope import component
from zope import interface

from ZODB.interfaces import IBroken
from ZODB.POSException import POSError

from nti.dataserver.interfaces import ISystemUserPrincipal
from nti.dataserver.interfaces import IPrincipalMetadataObjectsIntIds

def get_uid(obj, intids=None):
	intids = component.getUtility(zope.intid.IIntIds) if intids is None else intids
	try:
		if IBroken.providedBy(obj):
			logger.warn("ignoring broken object %s", type(obj))
		else:
			uid = intids.queryId(obj)
			if uid is None:
				logger.warn("ignoring unregistered object %s", obj)
			else:
				return uid
	except (POSError):
		logger.error("ignoring broken object %s", type(obj))
	return None

@component.adapter(ISystemUserPrincipal)
@interface.implementer(IPrincipalMetadataObjectsIntIds)
class _CoursesPrincipalObjectsIntIds(object):

	__slots__ = ()
	
	def __init__(self, *args, **kwargs):
		pass

	def iter_intids(self, intids=None):
		pass

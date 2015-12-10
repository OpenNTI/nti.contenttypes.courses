#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 14

from zope import component

from zope.component.hooks import site as current_site

from persistent.mapping import PersistentMapping

from nti.assessment.interfaces import IQAssessmentPolicies

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.site.hostpolicy import get_all_host_sites

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		for site in get_all_host_sites():
			with current_site(site):
				catalog = component.queryUtility(ICourseCatalog)
				if catalog is None:
					continue

				for entry in catalog.iterCatalogEntries():
					course = ICourseInstance(entry)
					if ILegacyCourseInstance.providedBy(course):
						continue

					policies = IQAssessmentPolicies(course)
					for ntiid in policies.assessments():
						data = policies[ntiid]
						if data is not None and not isinstance(data, PersistentMapping):
							data = PersistentMapping(data)
							policies[ntiid] = data

	logger.info('contenttypes.courses evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 14 by making assessment policices persistent mappings
	"""
	do_evolve(context, generation)
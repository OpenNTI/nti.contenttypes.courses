=====================
On-Disk Course Layout
=====================

This document describes the on-disk layout of new-style courses, which
is intended to be simple and flexible.


Concepts
========

Objects called :dfn:`course instances` are a particular manifestation of an
abstract *course design* or *course template*. It is the *course
instance* in which a student enrolls and which an instructors teaches.
For example, the abstract course called "CLC 3403" may be taught in
the fall of each year; a student does not enroll in the abstract
course "CLC 3403," he enrolls in "CLC 3403 Fall 2014 Section 1."

.. note:: Ideally, these two concepts would be fully separate and we
		  would be able to instantiate and customize a template into a
		  full instance at any given time. Currently, however, this is
		  not fully the case. Thus this document describes how course
		  instances are defined without going into detail on
		  templates.

Course instances are objects that live in the NTI database, where they
record enrollments, manage a gradebook, host class discussions, etc. A
particular course instance exists in exactly one *site,* and is only
accessible to people enrolled in, instructing, or administering it.

Each course instance is associated with a :dfn:`course catalog entry`.
The catalog entry provides the metadata about the course, useful to
potential students, such as a description, weekly schedule, etc.
Typically the catalog entry is visible and browsable to everyone, but
in certain instances it may be restricted or hidden (see below).
Course catalog entries also live in the NTI database.

Any course instance may be broken down into several smaller parts
called :dfn:`course sub-instances`, or, simply, *sections*. In
general, if a section doesn't specify some piece of information on its
own, it will inherit the information from its parent course; specifics
will be discussed below (one notable non-inherited piece of
information are the discussions).

A course instance is associated with one or more *content packages*
(sometimes known as "books") from the server's library. These content
packages form the course's *content package bundle*. In theory, the
content packages and bundles may exist and be accessed independently of
the course; in particular, a course may stitch together various small
pieces of any existing content to form its outline.

.. warning:: At this writing, no UI supports more than one single
			 content package per course. That is, the bundle can only
			 contain one content package.

.. warning:: The content packages used by courses **MUST** be
			 installed in the site library; they **MUST NOT** be
			 installed in the global library.

.. note:: The content packages have specific ACL requirements. See
		  :ref:`bundle_meta_info.json` for details.

A course has a :dfn:`course outline` or *syllabus* which consists of
titles (and availability information) of *units* and *lessons*, each
of which points (via NTIID) to a particular piece of the content
package.

Synchronization
---------------

If the course instance and its catalog entry are part of the NTI
database, how do they get there in the first place, and how are they
maintained if changes need to occur?

One way would be to manage this through-the-web (with a Web UI).
Although this is certainly feasible to implement, it makes it hard to
manage an evaluation/testing process.

Instead, our process relies on reading the information from files and
directories on disk and updating the objects in the database when
specifically requested by an administrator. The remainder of this
document will describe these files and directories.

.. tip:: The files and directories containing this information are
		 ideally suited to being stored in version control.

.. note:: For synchronization to work correctly, file and directory
		  modification dates must be reliable.

Directory Structure
===================

As mentioned, all courses are contained within a single site. This is
accomplished on-disk by having the files and directories that make up
a course exist within the on-disk library for that site. A typical
layout to define sites might look like this::

	DataserverGlobalLibrary/
	    ... # globally-visible content lives here
	    sites/ # container for sites
	        platform.ou.edu/ # each directory is a site directory
	            ... # content visible to this site and children live here
	        ou-alpha.nextthought.com/
	        janux.ou.edu/

.. note:: Sites are arranged in a hierarchy (parent-child
		  relationship). Objects in a parent are visible when using
		  the child site, and objects in a child site can override the
		  same object in the parent site (by matching its name). This
		  can be convenient for testing and evaluation. In this
		  example, ``platform.ou.edu`` is a base site, and both
		  ``ou-alpha.nextthought.com`` and ``janux.ou.edu`` extend it.

Inside the global library (``DataserverGlobalLibrary``) are content
packages, and the special directory ``sites``. Inside the ``sites``
directory are directories named for each site (*site directories*).
Inside each site directory exist the content packages visible to that
site.

There are a few special directories that can exist inside a site
directory::

	platform.ou.edu/
	    ... # content
	    ContentPackageBundles/ # content bundles, not relevant here
	    Courses/ # a site course directory

The one we are concerned with is called ``Courses``. This is the
site's course directory, or simply the course directory. All the
course instances available within the site (and children sites) are
defined by the structure inside this directory.

Courses Directory
-----------------

Inside the course directory are :dfn:`administrative levels` or
*organizational directories*. These are simply directories, nested to
any depth, that are used for organizing and namespacing the course
instances. A good practice is to use at least one level of
organizational directories to contain courses, named after the
academic term of the course::

	platform.ou.edu/
	    Courses/
	        Fall2013/ # org directory
	            CLC 3403/ # course directory
	            CHEM 4970/ # course directory
	        Spring2014/
	        Summer2014/
	        Fall2014/
	            CLC 3403/ # course directory

.. note:: In the future, the layout of these directories may be used
		  to help the UI group entries for display purposes.

Each organizational directory can be used to manage permissions. This
can be used to represent the course provider's administrative
structure and assign permissions to, for example, department heads,
with a layout like this::

	platform.ou.edu/
	    Courses/
	        PHIL/
                Fall2013/
                Fall2014/

.. note:: The administrative level permissioning is not actually
		  implemented at this time.

.. warning:: At any given level of the directory tree, names must be
			 unique (obviously; this is enforced by the filesystem)
			 and they must not conflict when spaces, special
			 characters and capitilization are ignored. For example,
			 you must not have two directories named ``CLC_3403`` and
			 ``CLC 3403``. Silent errors may result.

.. danger:: The directory structure is critical and **CANNOT** be
			changed after imported into the database. Renaming or
			moving a directory is the same thing as **deleting** the
			old directory (and any associated courses!) and creating a
			brand new directory. The directory structure becomes part
			of the permanent NTIID identifiers for objects.

Course Directory
^^^^^^^^^^^^^^^^

The directories that actually define a course instance are called
:dfn:`course directories`. These are a directory within an
organizational directory and are identified by the presence of a file
named ``bundle_meta_info.json``. In other words, any directory (within
the ``Courses`` directory) containing a ``bundle_meta_info.json`` file
defines a course instance.

Course directories **SHOULD** be named to match the
``ProviderUniqueID`` (more on that later). For example::

	platform.ou.edu/
	    Courses/
	        Fall2014/
	            CLC 3403/
	                bundle_meta_info.json

Course Directory Contents
=========================

With all the preliminaries about structuring the site and courses
directories out of the way, we can now address the contents of a
course directory, or what actually defines a course instance.

This section will describe each file that may have meaning within a
course directory. Full information is available in the source for
:mod:`nti.contenttypes.courses._synchronize`.

.. _bundle_meta_info.json:

``bundle_meta_info.json`` (required)
------------------------------------

This is the file that actually defines a course instance by relating
it to the content that it uses. A directory containing this file is a
course instance. This file is a standard bundle file as defined by
:mod:`nti.contentlibrary.bundle`::

	{
	    "ntiid": "tag:nextthought.com,2011-10:NTI-Bundle-ABundle",
	    "ContentPackages": ["tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california."],
	    "title": "A Title"
	}

.. note:: The NTIID, while currently required, will be ignored and/or
		  overwritten by an automatically generated ID in the future.
		  No client or server component should rely on this value.

.. note:: In the future, we expect to be able to reference existing
		  content package bundles instead of defining new one for each
		  course.

.. warning:: Recall that current UIs can only handle a single content
			 package being defined here.

.. caution:: If the content packages need to be permissioned to not be
			 publically visible without being enrolled in the course,
			 the ACL file **MUST** exist, but **MUST NOT** contain a
			 default-deny entry. Instead, it can contain an entry for
			 nextthought.com; a default-deny entry is added
			 automatically. Users enrolled in the course will be
			 automatically added to the groups that can access the content.

.. danger:: The packages referenced by a course **MUST NOT** change
			after the course is installed and has users enrolled.
			Doing so will result in stale permissions. (This is a
			limitation that can be fixed given time.)

``bundle_dc_metadata.xml`` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If present, this file is a standard Dublin Core XML file containing
additional metadata about the content bundle.

``course_info.json`` (semi-optional)
------------------------------------

Most of the information that fills in the course catalog entry comes
from this file. Full information is in :mod:`nti.contenttypes.courses._catalog_entry_parser`.

.. note:: For legacy migration convenience, if this file is not
          present in the course directory, it will be looked for in
          the content packages of the content bundle.

.. note:: Any NTIID value in this file is ignored.

The ``is_non_public`` key is a boolean that determines whether this
course and catalog entry is public, or restricted to those that are
enrolled in it through some other means.

.. warning:: Unlike legacy courses, the ``instructors`` field **DOES
			 NOT** influence course permissioning or course roles. It
			 is simply for display purposes in the UI. Therefore, anyone
			 can be listed here with no consequence. The real
			 information comes from the file :ref:`role_info.json`

Other possible keys:

.. list-table::
	:header-rows: 1

	* - Key
	  - Catalog Entry
	  - Example
	  - Notes
	* - id
	  - ProviderUniqueID
	  - CLC 3403
	  - Should match the directory name.
	* - InstructorsSignature
	  - InstractuorsSignature
	  - Dr Kyle Harper

		Provost

		University Of Oklahoma
	  - The sign-off used in emails sent from this course; if not provided, an automatic value is used.
	* - school
	  - ProviderDepartmentTitle
	  - Department of Classics and Letters at the University of Oklahoma
	  - Used in emails, must be the fully desired title
	* - isPreview
	  - Preview
	  - true
	  - An optional field that can be used to force a course to appear as a preview course, even if its start date has passed.
	* - is_non_public
	  - Internal ACL; not in CCE
	  - true
	  - If provided and ``true``, then only people already enrolled in the course have access to view the CCE.


``dc_metadata.xml`` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If present, this file is a standard Dublin Core XML file that can
contain extra metadata for the course catalog entry, such as title and
description. Any values present here will override those found in
``course_info.json``; this can be especially handy in the legacy
migration case.

``course_outline.xml`` (semi-optional)
--------------------------------------

The information that fills in the course outline is found in this XML
file. Full information is in
:mod:`nti.contenttypes.courses._outline_parser`.

.. note:: For legacy migration convenience, if this file is not
		  present in the course directory, it will be read from the
		  content package's ToC.

.. _role_info.json:

``role_info.json`` (semi-required)
----------------------------------

This file defines who has access to the administrative functions of
the course, such as the gradebook. It maps from role name to
permission to a list of users given or denied that role. It is
inherited (important for sections). Only the roles documented here are
supported. For example::

	{
          "nti.roles.course_instructor": {
                "allow": ["harp4162"],
                "deny": ["steve.johnson@nextthought.com"]
          },
          "nti.roles.course_ta": {
                "allow": ["jmadden"]
          }
	}

``vendor_info.json`` (optional)
-------------------------------

This optional file presents information that is use in particular
vendor-specific workflows. Each top-level key in the dictionary names
a vendor by convention (internal NTI information will be identified by
``NTI``; ``OU`` is another well known key), and the contents of the
dictionary are otherwise uninterpreted. See the particular workflow
documentation for what keys might be used.

::

	{
		"OU": {
            {"IMS": {"sourcedid": 12345, "source": SMS}},
            "CRN": "ABCD",
            "term_code": 10
		}
	}

``assignment_date_overrides.json`` (optional)
---------------------------------------------

This optional file changes the dates at which assignments are
available and/or no longer available. It maps from the NTIID of an
assignment to a dictionary giving the beginning and ending dates of
availability. The information in this file replaces the data for the
assignments specified within this course, (but does not change
anything about which assignments are available).

::

   {
         "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle":
	         {"available_for_submission_beginning": "2014-01-22T06:00:00Z"}
   }

.. note:: Given that currently content packages are where assignments
		  are defined, and that there is one content package per
		  course, and that content packages are not reused across
		  courses yet, this is actually only implemented for course
		  sections. The primary course uses the dates from the content
		  package.

``presentation-assets/`` (optional)
-----------------------------------

If present, this directory is a standard presentation assets directory
containing convention-based images for different platforms. This will
be returned as the ``PlatformPresentationResources`` value on the
catalog entry.

.. note:: For legacy migration convenience, if this directory is not
		  present, it will be searched for within the content packages
		  of the course.


Course Sections
===============

If a course instance directory contains a directory called
``Sections``, then the contents of each of those directories creates a
course section (the names are unimportant, but again, **CANNOT** be
changed)::

	platform.ou.edu/
	    Fall2014/
	        CLC 3403/
                bundle_meta_info.json
                Sections/
                   01/
                   02/

As mentioned before, most of the information about a section can be
inherited from its course. This portion of the document will describe
in detail what is inherited and what can be overridden, and how.

A course section is laid out much like a course itself, and optionally
all of the files (except ``bundle_meta_info.json``) may be present. At
least one of the files (typically ``role_info.json``) **MUST** be
present to be identified as a course section.

course_info.json
	This file is optional. If it is present, only the keys that are
	different from the course should be specified. For example, it
	might specify the ``ProviderUniqueID`` and the ``instructors``.
	Anything left unspecified will be inherited from the course.

course_outline.xml
	If this file is present, it *replaces* the outline of the parent
	course. If it is not present, the same outline of the parent
	course will be used.

role_info.json
	If this file is present, it grants instructor or TA permissions.
	This file will usually be present. Remember that the permissions
	are additive, so permissions from the parent course will be
	available (or denied) here unless explicitly overridden.

vendor_info.json
	The information in these files is **never** inherited. Vendor
	information must be set on a course-by-course or
	section-by-section basis.

assignment_date_overrides.json
	The information in these files is **never** inherited. Assignment
	information must be set on a course-by-course or
	section-by-section basis.

presentation-assets/
	This directory of assets is used for this course section. It
	may contain images of this section's instructors, for example.

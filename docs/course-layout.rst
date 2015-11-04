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

.. warning:: At this writing, no UI fully supports more than one single
			 content package per course. That is, the bundle can only
			 contain one content package.

.. caution:: At this writing, certain portions of the server may not
			 fully support more than one content package per course or
			 using the same content package in multiple distinct
			 courses. That is, the bundle can only contain one content
			 package.

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
instances; *at least one level is required*. A good practice is to use
at least one level of organizational directories to contain courses,
named after the academic term of the course::

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
	    "ContentPackages": ["tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california."],
	    "title": "A Title"
	}

.. note:: Regular (non-course) bundles are required to specify an
		  NTIID. However, any NTIID, specified here is ignored and
		  overwritten by an automatically generated ID. No client or
		  server component should rely on this value, and it's best to
		  leave it out.

.. note:: In the future, we expect to be able to reference existing
		  content package bundles instead of defining new one for each
		  course.

.. warning:: Recall that current UIs can only fully handle a single
			 content package being defined here.

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
            {"IMS": {"sourcedid": ["A String", "Or a list of strings"]
					"source":     SMS}},
            "CRN": "ABCD",
            "Term": 10
        },
        "NTI": {
            "EnrollmentMap": {
                "ForCreditNonDegree": "section-name"
            },
        	"SharingScopesDisplayInfo": {
           	 	"Public": {
                	"alias": "From Vendor Info",
                	"realname": "",
                	"avatarURL": "/foo/bar.jpg"
            },
            "DefaultSharingScope" : "Parent/Public",
            "show_assignments_by_outline": false
        }
    }

Known NTI keys are documented here:

EnrollmentMap
	A dictionary mapping enrollment scopes to the section data
	that should handle that scope. Any attempts to enroll in this
	course with that scope will instead be directed to this named
	section of this course. A section data is either a string with
	a section name or a dictionary with the sections_names vs a
	maximum seat count. A section is filled before the next one.
	If all sections are full, the section with the least enrollments
	if chosen.

	Only valid at the main course level, and only intended to solve
	the use case of directing certain for-credit enrollments in a
	public course to a specific section that holds all types of
	for-credit enrollments. Typically the target section will be
	marked as ``non_public``, while the course itself will be public.

	This is validated at sync time, and the name of the scope and
	the name of the section must both be valid and exist.

	.. danger:: This mapping **SHOULD NOT** change after enrollment has
				 started. No attempt is made to adjust enrollments in
				 that case.
Forums
	A dictionary, valid at any level, containing information
	pertaining to how discussion forums should automatically be
	created. This is optional, with defaults in code, and valid at all
	levels. Most of these cannot be usefully changed after forums have
	been automatically created for the first time.

	* ``HasOpenDiscussions``, ``HasInClassDiscussions``,
	  ``HasOpenAnnouncements``, ``HasInClassAnnouncements``: All of
	  these are booleans (defaulting to true) that determine whether
	  the corresponding forum is automatically created when a course
	  discussion is added. In the case of discussions, if the value is
	  false, then no discussion will be put in that forum; if you
	  change that value after the course is running, future
	  discussions will stop being put there, even if the forum already
	  exists.

	* ``OpenDiscussionsDisplayName``,
	  ``InClassDiscussionsDisplayName``,
	  ``OpenAnnouncementsDisplayName``,
	  ``InClassAnnouncementsDisplayName``: All of these are strings
	  that, if set, will override the default display name for these
	  items the first time the forum is created; after that, you must
	  use the API or GUI to change them.
	  
	* ``AutoCreate`: A boolean that determine whether
	  the corresponding boards are automatically created if course 
	  disussions are defined

SharingScopesDisplayInfo
	A dictionary, valid at any level, containing optional information
	about how the auto-created sharing scopes should be displayed.

	It contains dictionaries named for each sharing scope (e.g.,
	"Public" and "ForCredit", see
	:py:mod:`nti.contenttypes.courses.interfaces`). The ``alias`` and
	``realname`` are strings, which, if present and non-empty, exactly
	specify those values (replacing completely the automatic
	generation). Likewise, ``avatarURL`` is a URL or path giving an
	image to display.

DefaultSharingScope
	A string that is only really valid at the section level. This
	could be set to an NTIID that will be exposed as the
	'DefaultSharingScope' when exposed to clients.  As an alternative
	to an NTIID, the actual scope can be specified.

	If this exists in a section, this string could specify two
	bits of information: 'Parent' indicates that the parent
	instance's scope should be used.  Following the '/' delimiter,
	the actual parent scope to be used is specified.

show_assignments_by_outline
	A bool indicating whether or not this course has assignments returned
	by assignments by outline node.  Useful for hiding the assignments tab.
	Note: it is invalid to set this to false and have assignments in the course

``assignment_policies.json`` (optional)
---------------------------------------------

This optional file is used to determine policy changes for
assignments, including the dates at which assignments are available
and/or no longer available. It maps from the NTIID of an assignment to
a dictionary giving the beginning and ending dates of availability as
well as automatic grading and other information. The information in this file
replaces the data for the assignments specified within this course,
(but does not change anything about which assignments are available).

::

	{
		"tag:nextthought.com,2011-10:OU-NAQ-CS1300_Power_and_Elegance_of_Computational_Thinking.naq.asg.assignment:3.3_Exercise_Sound": {
		    "Title": "Exercise: Learning to Make Sound",
		    "auto_grade": {
		        "total_points": 20
		    },
		    "available_for_submission_beginning": "2014-01-13T06:00:00Z",
		    "available_for_submission_ending":    "2014-03-03T05:59:00Z",
		    "excluded": false,
		    "student_nuclear_reset_capable": false,
		},
	}

The automatic grading information is being defined on an as-needed
basis. The supported values are
	``total_points`` which defines a value to which all the equally-weighted questions will
	be normalized. (This value will be reflected in the ``Grade`` object's
	``AutoGradeMax`` property.) It can be defined individually for each
	assignment; tool support lets you easily normalize all assignments the
	same. It can be explicitly set to ``null`` to disable auto-grading and
	better merge with the tool.

	Aditionally (optionally)
	``name`` which points to a defined registered named policy ``IPendingAssessmentAutoGradePolicy`` object.
	 A special case when name is ``pointbased`` which requires additional information as follows:
	 ``questions`` which defines map of question ids vs number of points. A special key called ``default``
	 points to the default number of points to a question not specifed in this map

	 {
    "tag:nextthought.com,2011-10:OU-NAQ-CS1300_Power_and_Elegance_of_Computational_Thinking.naq.asg.assignment:3.3_Exercise_Sound": {
        "Title": "Exercise: Learning to Make Sound",
        "auto_grade": {
			name: "pointbased",
            "total_points": 20,
            "questions": {
            	"default":1,
            	"tag:nextthought.com,2011-10:OU-NAQ-CS1300_Power_and_Elegance_of_Computational_Thinking.naq.qid.verification.05":10
            }
        },
        ...
      }

Another known key (defined by
:py:mod:`nti.app.assessment.assignment_filters`) is ``excluded``, a
boolean, which, if given, tells whether the assignment should not be
visible in this course (neither to students nor the instructor).

Yet another key (defined by :py:mod:`nti.app.assessment.history`) is
``student_nuclear_reset_capable``, a boolean, which, if given, tells
whether the nuclear reset option (deleting the entire assignment
history) should be available to students on this assignment. The
default is false.

This file is meant to be automatically generated and then
human-edited, but merged with additional automatic generated content:

.. command-output:: nti_extract_assessments -h

.. note:: Given that currently content packages are where assignments
		  are defined, and that there is one content package per
		  course, and that content packages are not reused across
		  courses yet, changing dates is only recommended for course
		  sections. The primary course should use the dates from the
		  content package. The primary course can, however, fully use
		  the other policy information.

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

	
Course Discussions
===============

If a course instance directory contains a directory called
``Discussions``, then the json files of that directory defines the 
discussions in the course:

	platform.ou.edu/
	    Fall2014/
	        CLC 3403/
                bundle_meta_info.json
                Discussions/
                   01.json
                   02.json
	
A course discussion is json file with the following format.

::
	{
		"Class": "Discussion",
		"MimeType": "application/vnd.nextthought.courses.discussion",
		"body": ["<html><body><span>The United States' Trade Promotion Authority><\/body><\/html>"],
		"tags": [
			"japan",
			"trade",
			"pacific"
		],
		"scopes": ["All"],
		"title": "U.S.: A Potential Breakthrough in Trans-Pacific Trade Talks"
	}

The ``Class`` and ``MimeType`` fields are always set to 'Discussion' and 'application/vnd.nextthought.courses.discussion'

The ``body`` field is an array of [html] text

The ``tags`` field is an array of the discussion tags

The ``scopes`` fields refers to the enrollment scopes associated with this discussion. That is students in a particular
scope have access to the discussion. ``All`` is a special string to indicate all scopes

The ``title`` fiels is the discussion title.


from setuptools import setup, find_packages
import codecs

VERSION = '0.0.0'

entry_points = {
    "z3c.autoinclude.plugin": [
		#'target = nti.dataserver.contenttypes',
		# NOTE: We cannot be auto-included by the dataserver
		# content types because we ourself include
		# nti.appserver for testing. This leads to configuration
		# conflicts due to the cycle.
		'target = nti.app',
	],
}

setup(
    name = 'nti.contenttypes.courses',
    version = VERSION,
    author = 'Jason Madden',
    author_email = 'jason@nextthought.com',
    description = "Support for storing course information",
    long_description = codecs.open('README.rst', encoding='utf-8').read(),
    license = 'Proprietary',
    keywords = 'pyramid preference',
    #url = 'https://github.com/NextThought/nti.nose_traceback_info',
    classifiers = [
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
		'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.3',
        'Topic :: Software Development :: Testing'
		'Framework :: Pyramid',
        ],
	packages=find_packages('src'),
	package_dir={'': 'src'},
	namespace_packages=['nti', 'nti.contenttypes'],
	install_requires=[
		'setuptools',
		# NOTE: We actually depend on nti.dataserver
		# as well, but for the sake of legacy
		# deployments, we do not yet declare that.
		# We will declare it when everything is in
		# buildout
	],
	entry_points=entry_points
)

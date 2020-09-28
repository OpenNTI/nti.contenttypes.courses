import codecs
from setuptools import setup, find_packages

entry_points = {
    "z3c.autoinclude.plugin": [
        'target = nti.dataserver.contenttypes',
    ],
}


TESTS_REQUIRE = [
    'nti.testing',
    'zope.dottedname',
    'zope.testrunner',
    'nti.dataserver[test]'
]


def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.contenttypes.courses',
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="Support for storing course information",
    long_description=(_read('README.rst') + '\n\n' + _read("CHANGES.rst")),
    license='Apache',
    keywords='courses',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    url="https://github.com/NextThought/nti.contenttypes.courses",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.contenttypes'],
    install_requires=[
        'setuptools',
        'BTrees',
        'isodate',
        'nti.assessment',
        'nti.base',
        'nti.common',
        'nti.containers',
        'nti.contentfragments',
        'nti.contentlibrary',
        'nti.contenttypes.completion',
        'nti.contenttypes.credit',
        'nti.contenttypes.reports',
        'nti.coremetadata',
        'nti.dataserver',
        'nti.dublincore',
        'nti.externalization',
        'nti.invitations',
        'nti.links',
        'nti.metadata',
        'nti.mimetype',
        'nti.namedfile',
        'nti.ntiids',
        'nti.property',
        'nti.publishing',
        'nti.recorder',
        'nti.schema',
        'nti.site',
        'nti.traversal',
        'nti.wref',
        'nti.zope_catalog',
        'persistent',
        'requests',
        'simplejson',
        'six',
        'zc.intid',
        'ZODB',
        'zope.annotation',
        'zope.authentication',
        'zope.cachedescriptors',
        'zope.component',
        'zope.container',
        'zope.dublincore',
        'zope.event',
        'zope.generations',
        'zope.i18nmessageid',
        'zope.intid',
        'zope.interface',
        'zope.keyreference',
        'zope.lifecycleevent',
        'zope.location',
        'zope.mimetype',
        'zope.proxy',
        'zope.schema',
        'zope.security',
        'zope.securitypolicy',
        'zope.site',
        'zope.traversing',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
        'docs': [
            'Sphinx',
            'repoze.sphinx.autointerface',
            'sphinx_rtd_theme',
        ],
    },
    entry_points=entry_points,
)

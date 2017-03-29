from setuptools import setup, find_packages
import codecs

VERSION = '0.0.0'

entry_points = {
    "z3c.autoinclude.plugin": [
        'target = nti.dataserver.contenttypes',
    ],
}

setup(
    name='nti.contenttypes.courses',
    version=VERSION,
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="Support for storing course information",
    long_description=codecs.open('README.rst', encoding='utf-8').read(),
    license='Proprietary',
    keywords='pyramid preference',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython'
    ],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['nti', 'nti.contenttypes'],
    install_requires=[
        'setuptools',
        'nti.assessment',
        'nti.base',
        'nti.common',
        'nti.containers',
        'nti.contentfragments',
        'nti.contentlibrary',
        'nti.coremetadata',
        'nti.dublincore',
        'nti.externalization',
        'nti.links',
        'nti.metadata',
        'nti.mimetype',
        'nti.namedfile',
        'nti.ntiids',
        'nti.property',
        'nti.recorder',
        'nti.schema',
        'nti.site',
        'nti.traversal',
        'nti.zope_catalog',
    ],
    entry_points=entry_points
)

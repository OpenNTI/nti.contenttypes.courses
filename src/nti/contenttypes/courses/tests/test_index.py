import fudge

from hamcrest import is_
from hamcrest import assert_that
from hamcrest import has_length
from hamcrest import has_items

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.index import InstructorSetIndex
from nti.contenttypes.courses.index import EditorSetIndex

from nti.contenttypes.courses.tests import CourseLayerTest


class TestIndex(CourseLayerTest):

    @fudge.patch('nti.contenttypes.courses.index.get_course_instructors')
    def testInstructorSetIndex(self, mock_course_instructors):
        index = InstructorSetIndex()
        assert_that(list(index.ids()), has_length(0))
        assert_that(list(index.values()), has_length(0))

        inst = ContentCourseInstance()

        mock_course_instructors.is_callable().returns([])
        index.index_doc(1, inst)
        assert_that(list(index.ids()), has_length(0))
        assert_that(list(index.values()), has_length(0))

        mock_course_instructors.is_callable().returns(['test001', 'test002'])
        index.index_doc(1, inst)
        assert_that(list(index.ids()), is_([1]))
        assert_that(list(index.values()), has_length(2))

        mock_course_instructors.is_callable().returns(['test001', 'test002', 'test003'])
        index.index_doc(1, inst)
        assert_that(list(index.ids()), is_([1]))
        assert_that(list(index.values()), has_length(3))
        assert_that(list(index.values()), has_items('test001', 'test002', 'test003'))

        mock_course_instructors.is_callable().returns([])
        index.index_doc(1, inst)
        assert_that(list(index.ids()), has_length(0))
        assert_that(list(index.values()), has_length(0))

        mock_course_instructors.is_callable().returns(['test001'])
        index.index_doc(1, inst)
        mock_course_instructors.is_callable().returns(['test001', 'test002'])
        index.index_doc(2, inst)
        assert_that(list(index.ids()), has_length(2))
        assert_that(list(index.ids()), has_items(1, 2))
        assert_that(list(index.values()), has_length(2))
        assert_that(list(index.values()), has_items('test001', 'test002'))

    @fudge.patch('nti.contenttypes.courses.index.get_course_editors')
    def testEditorSetIndex(self, mock_course_editors):
        index = EditorSetIndex()
        assert_that(list(index.ids()), has_length(0))
        assert_that(list(index.values()), has_length(0))

        inst = ContentCourseInstance()

        mock_course_editors.is_callable().returns([])
        index.index_doc(1, inst)
        assert_that(list(index.ids()), has_length(0))
        assert_that(list(index.values()), has_length(0))

        mock_course_editors.is_callable().returns(['test001', 'test002'])
        index.index_doc(1, inst)
        assert_that(list(index.ids()), is_([1]))
        assert_that(list(index.values()), has_length(2))

        mock_course_editors.is_callable().returns(['test001', 'test002', 'test003'])
        index.index_doc(1, inst)
        assert_that(list(index.ids()), is_([1]))
        assert_that(list(index.values()), has_length(3))
        assert_that(list(index.values()), has_items('test001', 'test002', 'test003'))

        mock_course_editors.is_callable().returns([])
        index.index_doc(1, inst)
        assert_that(list(index.ids()), has_length(0))
        assert_that(list(index.values()), has_length(0))

        mock_course_editors.is_callable().returns(['test001'])
        index.index_doc(1, inst)
        mock_course_editors.is_callable().returns(['test001', 'test002'])
        index.index_doc(2, inst)
        assert_that(list(index.ids()), has_length(2))
        assert_that(list(index.ids()), has_items(1, 2))
        assert_that(list(index.values()), has_length(2))
        assert_that(list(index.values()), has_items('test001', 'test002'))

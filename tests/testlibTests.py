#
# Copyright 2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from testlib import AssertingLock
from testlib import VdsmTestCase
from testlib import maybefail
from testlib import recorded
from testlib import permutations, expandPermutations, PERMUTATION_ATTR


class AssertNotRaisesTests(VdsmTestCase):

    def test_contextmanager_fail(self):
        with self.assertRaises(self.failureException):
            with self.assertNotRaises():
                raise Exception("test failure")

    def test_contextmanager_pass(self):
        with self.assertNotRaises():
            pass

    def test_inline_fail(self):
        def func():
            raise Exception("test failure")
        with self.assertRaises(self.failureException):
            self.assertNotRaises(func)

    def test_inline_pass(self):
        def func():
            pass
        self.assertNotRaises(func)


class AssertingLockTests(VdsmTestCase):

    def test_free(self):
        lock = AssertingLock()
        with lock:
            pass

    def test_locked(self):
        lock = AssertingLock()
        with self.assertRaises(AssertionError):
            with lock:
                with lock:
                    pass


class RecordedTests(VdsmTestCase):

    def setUp(self):
        try:
            del Recorded.__class_calls__
        except AttributeError:
            pass

    def test_no_args(self):
        obj = Recorded()
        obj.no_args()
        self.assertEqual(obj.__calls__, [("no_args", (), {})])

    def test_args(self):
        obj = Recorded()
        obj.args(1, 2)
        self.assertEqual(obj.__calls__, [("args", (1, 2), {})])

    def test_kwargs(self):
        obj = Recorded()
        obj.kwargs(a=1, b=2)
        self.assertEqual(obj.__calls__, [("kwargs", (), {"a": 1, "b": 2})])

    def test_kwargs_as_args(self):
        obj = Recorded()
        obj.kwargs(1, 2)
        self.assertEqual(obj.__calls__, [("kwargs", (1, 2), {})])

    def test_no_kwargs(self):
        obj = Recorded()
        obj.args_and_kwargs(1, 2)
        self.assertEqual(obj.__calls__, [("args_and_kwargs", (1, 2), {})])

    def test_some_kwargs(self):
        obj = Recorded()
        obj.args_and_kwargs(1, 2, c=3)
        self.assertEqual(obj.__calls__,
                         [("args_and_kwargs", (1, 2), {"c": 3})])

    def test_args_as_kwargs(self):
        obj = Recorded()
        obj.args_and_kwargs(a=1, b=2)
        self.assertEqual(obj.__calls__,
                         [("args_and_kwargs", (), {"a": 1, "b": 2})])

    def test_flow(self):
        obj = Recorded()
        obj.no_args()
        obj.kwargs(a=1)
        self.assertEqual(obj.__calls__, [
            ("no_args", (), {}),
            ("kwargs", (), {"a": 1}),
        ])

    def test_class_method_via_class(self):
        Recorded.class_method('a', b=2)
        self.assertEqual(Recorded.__class_calls__,
                         [('class_method', ('a',), {'b': 2})])

    def test_class_method_via_obj(self):
        obj = Recorded()
        obj.class_method('a', b=2)
        self.assertEqual(Recorded.__class_calls__,
                         [('class_method', ('a',), {'b': 2})])

    def test_class_method_flow(self):
        obj = Recorded()
        obj.class_method('a', b=2)
        obj.class_method_noargs()
        self.assertEqual(Recorded.__class_calls__, [
            ('class_method', ('a',), {'b': 2}),
            ('class_method_noargs', (), {}),
        ])

    def test_flow_mixed(self):
        obj = Recorded()
        obj.class_method('a', b=2)
        obj.args(1, 2)
        self.assertEqual(Recorded.__class_calls__, [
            ('class_method', ('a',), {'b': 2}),
        ])
        self.assertEqual(obj.__calls__, [
            ('args', (1, 2), {}),
        ])


class Recorded(object):

    @classmethod
    @recorded
    def class_method(cls, *a, **kw):
        pass

    @classmethod
    @recorded
    def class_method_noargs(cls):
        pass

    @recorded
    def args_and_kwargs(self, a, b, c=3, d=4):
        pass

    @recorded
    def args(self, a, b):
        pass

    @recorded
    def kwargs(self, a=1, b=2):
        pass

    @recorded
    def no_args(self):
        pass


@expandPermutations
class Permutated(object):

    @permutations([[1, 2], [3, 4]])
    def fn(self, a, b):
        return a, b


@expandPermutations
class SubPermuated(Permutated):

    @permutations([[1], [2]])
    def fn2(self, param):
        return param


class TestPermutationExpansion(VdsmTestCase):

    def setUp(self):
        self.instance = Permutated()

    def test_expand_new_methods(self):
        self.assertTrue(hasattr(self.instance, 'fn(1, 2)'))
        self.assertTrue(hasattr(self.instance, 'fn(3, 4)'))

    def test_remove_expanded_method(self):
        self.assertFalse(hasattr(self.instance, "fn"))

    def test_invoke_expanded_1(self):
        expanded_method = getattr(self.instance, "fn(1, 2)")
        self.assertEqual((1, 2), expanded_method())

    def test_invoke_expanded_2(self):
        expanded_method = getattr(self.instance, "fn(3, 4)")
        self.assertEqual((3, 4), expanded_method())

    def test_clear_permuations_attribute(self):
        fn = getattr(Permutated, 'fn(1, 2)')
        self.assertFalse(hasattr(fn, PERMUTATION_ATTR))


class TestSubPermuated(VdsmTestCase):

    def setUp(self):
        self.instance = SubPermuated()

    def test_super_method(self):
        expanded_method = getattr(self.instance, "fn(1, 2)")
        self.assertEqual((1, 2), expanded_method())

    def test_sub_method(self):
        expanded_method = getattr(self.instance, "fn2(1)")
        self.assertEqual(1, expanded_method())


class TestMaybefail(VdsmTestCase):

    def setUp(self):
        self.errors = {}

    @maybefail
    def method_name(self):
        return True

    def test_success(self):
        self.assertTrue(self.method_name())

    def test_error(self):
        self.errors["method_name"] = RuntimeError
        self.assertRaises(RuntimeError, self.method_name)
        self.assertRaises(RuntimeError, self.method_name)

    def test_recover(self):
        self.errors["method_name"] = RuntimeError
        self.assertRaises(RuntimeError, self.method_name)
        del self.errors["method_name"]
        self.assertTrue(self.method_name())

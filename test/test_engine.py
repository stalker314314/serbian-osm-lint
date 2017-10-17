# -*- coding: utf-8 -*-

import unittest

from osmread import Way
from unittest.mock import patch

from applicability import Applicability
from checks import AbstractCheck
from engine import CheckEngine, Result


class EveryEntity(Applicability):
    @staticmethod
    def is_entity_applicable(entity):
        return True


class NoEntity(Applicability):
    @staticmethod
    def is_entity_applicable(entity):
        return False


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.entity = Way(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, nodes=[])
        self.default_global_context = {'fix': False, 'map': 'Serbia', 'dry_run': True}

    def test_empty_engine(self):
        engine = CheckEngine([], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            results = engine.check_all()
            self.assertEqual(len(results), 0)
            self.assertEqual(do_entity_check_and_fix.call_count, 0)

    def test_engine_one_check_not_applicable(self):
        class OnlyCheck(AbstractCheck):
            applicable_on = [NoEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(OnlyCheck, self).__init__(entity_context)

            def do_check(self, entity):
                OnlyCheck.hit_check = OnlyCheck.hit_check + 1
                return ''

        engine = CheckEngine([OnlyCheck], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            results = engine.check_all()
            self.assertEqual(OnlyCheck.hit_check, 0)
            self.assertEqual(do_entity_check_and_fix.call_count, 0)
            self.assertEqual(len(results), 0)
            # Do again, but without filtering
            engine = CheckEngine([OnlyCheck], self.entity, self.default_global_context)
            results = engine.check_all(filter_not_checked=False)
            self.assertEqual(OnlyCheck.hit_check, 0)
            self.assertEqual(do_entity_check_and_fix.call_count, 0)
            self.assertEqual(len(results), 1)
            self.assertTrue(OnlyCheck.__name__ in results)
            result = results[OnlyCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.NOT_APPLICABLE)

    def test_engine_one_check_applicable(self):
        class OnlyCheck(AbstractCheck):
            applicable_on = [EveryEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(OnlyCheck, self).__init__(entity_context)

            def do_check(self, entity):
                OnlyCheck.hit_check = OnlyCheck.hit_check + 1
                return ''

        engine = CheckEngine([OnlyCheck], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            results = engine.check_all()
            self.assertEqual(do_entity_check_and_fix.call_count, 1)
            self.assertEqual(OnlyCheck.hit_check, 1)
            self.assertEqual(len(results), 1)
            self.assertTrue(OnlyCheck.__name__ in results)
            result = results[OnlyCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.CHECKED_OK)

    def test_engine_independent_check_not_applicable(self):
        """
        Tests that there are two checks, and independent one is not applicable.
        Dependent check should also fail and check should not get called on it.
        """
        class IndependentCheck(AbstractCheck):
            applicable_on = [NoEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(IndependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                IndependentCheck.hit_check = IndependentCheck.hit_check + 1
                return 'Error1'

        class DependentCheck(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [IndependentCheck]
            hit_check = 0

            def __init__(self, entity_context):
                super(DependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                DependentCheck.hit_check = DependentCheck.hit_check + 1
                return ''

        engine = CheckEngine([IndependentCheck, DependentCheck], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            results = engine.check_all()
            self.assertEqual(IndependentCheck.hit_check, 0)
            self.assertEqual(DependentCheck.hit_check, 0)
            self.assertEqual(do_entity_check_and_fix.call_count, 0)
            self.assertEqual(len(results), 0)

        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            # Now again, without filtering checks
            engine = CheckEngine([DependentCheck, IndependentCheck], self.entity, self.default_global_context)
            results = engine.check_all(filter_not_checked=False)
            self.assertEqual(IndependentCheck.hit_check, 0)
            self.assertEqual(DependentCheck.hit_check, 0)
            self.assertEqual(do_entity_check_and_fix.call_count, 0)
            self.assertEqual(len(results), 2)
            self.assertTrue(IndependentCheck.__name__ in results)
            self.assertTrue(DependentCheck.__name__ in results)

            result = results[IndependentCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.NOT_APPLICABLE)

            result = results[DependentCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.DEPENDENCY_NOT_SATISFIED)

    def test_engine_independent_check_not_satisfied(self):
        """
        Tests that there are two checks, and independent one is not satisfied.
        Dependent check should also fail and check should not get called on it.
        """
        class IndependentCheck(AbstractCheck):
            applicable_on = [EveryEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(IndependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                IndependentCheck.hit_check = IndependentCheck.hit_check + 1
                return 'Error1'

        class DependentCheck(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [IndependentCheck]
            hit_check = 0

            def __init__(self, entity_context):
                super(DependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                DependentCheck.hit_check = DependentCheck.hit_check + 1
                return ''

        engine = CheckEngine([DependentCheck, IndependentCheck], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            results = engine.check_all()
            self.assertEqual(IndependentCheck.hit_check, 1)
            self.assertEqual(DependentCheck.hit_check, 0)
            self.assertEqual(do_entity_check_and_fix.call_count, 1)
            self.assertEqual(len(results), 1)
            self.assertTrue(IndependentCheck.__name__ in results)
            result = results[IndependentCheck.__name__]
            self.assertEqual(len(result['messages']), 1)
            self.assertEqual(result['messages'][0], 'Error1')
            self.assertEqual(result['result'], Result.CHECKED_ERROR)
        # Now again, without filtering checks
        engine = CheckEngine([IndependentCheck, DependentCheck], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            IndependentCheck.hit_check = 0
            results = engine.check_all(filter_not_checked=False)
            self.assertEqual(IndependentCheck.hit_check, 1)
            self.assertEqual(DependentCheck.hit_check, 0)
            self.assertEqual(do_entity_check_and_fix.call_count, 1)
            self.assertEqual(len(results), 2)
            self.assertTrue(IndependentCheck.__name__ in results)
            self.assertTrue(DependentCheck.__name__ in results)

            result = results[IndependentCheck.__name__]
            self.assertEqual(len(result['messages']), 1)
            self.assertEqual(result['messages'][0], 'Error1')
            self.assertEqual(result['result'], Result.CHECKED_ERROR)

            result = results[DependentCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.DEPENDENCY_NOT_SATISFIED)

    def test_engine_dependent_check_not_applicable(self):
        """
        Tests that there are two checks, and independent one is OK and satisfied,
        but dependent check is not applicable.
        """
        class IndependentCheck(AbstractCheck):
            applicable_on = [EveryEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(IndependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                IndependentCheck.hit_check = IndependentCheck.hit_check + 1
                return ''

        class DependentCheck(AbstractCheck):
            applicable_on = [NoEntity]
            depends_on = [IndependentCheck]
            hit_check = 0

            def __init__(self, entity_context):
                super(DependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                DependentCheck.hit_check = DependentCheck.hit_check + 1
                return ''

        engine = CheckEngine([DependentCheck, IndependentCheck], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            results = engine.check_all()
            self.assertEqual(IndependentCheck.hit_check, 1)
            self.assertEqual(DependentCheck.hit_check, 0)
            self.assertEqual(do_entity_check_and_fix.call_count, 1)
            self.assertEqual(len(results), 1)
            self.assertTrue(IndependentCheck.__name__ in results)
            result = results[IndependentCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.CHECKED_OK)
        # Now again, without filtering checks
        engine = CheckEngine([DependentCheck, IndependentCheck], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            IndependentCheck.hit_check = 0
            results = engine.check_all(filter_not_checked=False)
            self.assertEqual(IndependentCheck.hit_check, 1)
            self.assertEqual(DependentCheck.hit_check, 0)
            self.assertEqual(do_entity_check_and_fix.call_count, 1)
            self.assertEqual(len(results), 2)
            self.assertTrue(IndependentCheck.__name__ in results)
            self.assertTrue(DependentCheck.__name__ in results)

            result = results[IndependentCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.CHECKED_OK)

            result = results[DependentCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.NOT_APPLICABLE)

    def test_engine_dependent_check_not_satisfied(self):
        """
        Tests that there are two checks, and independent one is OK and satisfied,
        but dependent check is not satisfied.
        """
        class IndependentCheck(AbstractCheck):
            applicable_on = [EveryEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(IndependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(DependentCheck.hit_check, 0)
                IndependentCheck.hit_check = IndependentCheck.hit_check + 1
                return ''

        class DependentCheck(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [IndependentCheck]
            hit_check = 0

            def __init__(self, entity_context):
                super(DependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(IndependentCheck.hit_check, 1)
                DependentCheck.hit_check = DependentCheck.hit_check + 1
                return 'Error2'

        engine = CheckEngine([DependentCheck, IndependentCheck], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            results = engine.check_all()
            self.assertEqual(IndependentCheck.hit_check, 1)
            self.assertEqual(DependentCheck.hit_check, 1)
            self.assertEqual(do_entity_check_and_fix.call_count, 2)
            self.assertEqual(len(results), 2)
            self.assertTrue(IndependentCheck.__name__ in results)
            self.assertTrue(DependentCheck.__name__ in results)

            result = results[IndependentCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.CHECKED_OK)

            result = results[DependentCheck.__name__]
            self.assertEqual(len(result['messages']), 1)
            self.assertEqual(result['messages'][0], 'Error2')
            self.assertEqual(result['result'], Result.CHECKED_ERROR)

    def test_engine_dependent_check(self):
        """
        Tests that there are two checks, and both are satisfied and OK.
        """
        class IndependentCheck(AbstractCheck):
            applicable_on = [EveryEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(IndependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(DependentCheck.hit_check, 0)
                IndependentCheck.hit_check = IndependentCheck.hit_check + 1
                return ''

        class DependentCheck(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [IndependentCheck]
            hit_check = 0

            def __init__(self, entity_context):
                super(DependentCheck, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(IndependentCheck.hit_check, 1)
                DependentCheck.hit_check = DependentCheck.hit_check + 1
                return ''

        engine = CheckEngine([DependentCheck, IndependentCheck], self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            results = engine.check_all()
            self.assertEqual(IndependentCheck.hit_check, 1)
            self.assertEqual(DependentCheck.hit_check, 1)
            self.assertEqual(do_entity_check_and_fix.call_count, 2)
            self.assertEqual(len(results), 2)
            self.assertTrue(IndependentCheck.__name__ in results)
            self.assertTrue(DependentCheck.__name__ in results)

            result = results[IndependentCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.CHECKED_OK)

            result = results[DependentCheck.__name__]
            self.assertEqual(len(result['messages']), 0)
            self.assertEqual(result['result'], Result.CHECKED_OK)

    def test_engine_circular_dependecies(self):
        """
        Tests that circular dependencies are not allowed.
        """
        class Check1(AbstractCheck):
            applicable_on = [EveryEntity]

            def __init__(self, entity_context):
                super(Check1, self).__init__(entity_context)

            def do_check(self, entity):
                return ''

        class Check2(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [Check1]

            def __init__(self, entity_context):
                super(Check2, self).__init__(entity_context)

            def do_check(self, entity):
                return ''

        class Check3(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [Check2]

            def __init__(self, entity_context):
                super(Check2, self).__init__(entity_context)

            def do_check(self, entity):
                return ''

        Check1.depends_on = [Check3]

        engine = CheckEngine([Check1, Check2, Check3], self.entity, self.default_global_context)
        try:
            engine.check_all()
            self.fail()
        except Exception as e:
            self.assertTrue('Circular' in str(e))

    def test_engine_complex_check_dependency_tree(self):
        """
        Test with multiple checks with following dependency tree:
        
                /-- G ----\
        A  --> D ----------> H
        B  --> E ---> F --/
        C  --------/
        """
        class CheckA(AbstractCheck):
            applicable_on = [EveryEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(CheckA, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(CheckD.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckG.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckH.hit_check, 0)
                CheckA.hit_check = CheckA.hit_check + 1
                return ''

        class CheckB(AbstractCheck):
            applicable_on = [EveryEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(CheckB, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(CheckE.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckF.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckH.hit_check, 0)
                CheckB.hit_check = CheckB.hit_check + 1
                return ''

        class CheckC(AbstractCheck):
            applicable_on = [EveryEntity]
            hit_check = 0

            def __init__(self, entity_context):
                super(CheckC, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(CheckF.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckH.hit_check, 0)
                CheckC.hit_check = CheckC.hit_check + 1
                return ''

        class CheckD(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [CheckA]
            hit_check = 0

            def __init__(self, entity_context):
                super(CheckD, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(CheckG.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckH.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckA.hit_check, 1)
                CheckD.hit_check = CheckD.hit_check + 1
                return ''

        class CheckE(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [CheckB]
            hit_check = 0

            def __init__(self, entity_context):
                super(CheckE, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(CheckF.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckH.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckB.hit_check, 1)
                CheckE.hit_check = CheckE.hit_check + 1
                return ''

        class CheckF(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [CheckE, CheckC]
            hit_check = 0

            def __init__(self, entity_context):
                super(CheckF, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(CheckH.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckB.hit_check, 1)
                unittest.TestCase('__init__').assertEquals(CheckE.hit_check, 1)
                unittest.TestCase('__init__').assertEquals(CheckC.hit_check, 1)
                CheckF.hit_check = CheckF.hit_check + 1
                return ''

        class CheckG(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [CheckD]
            hit_check = 0

            def __init__(self, entity_context):
                super(CheckG, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(CheckH.hit_check, 0)
                unittest.TestCase('__init__').assertEquals(CheckD.hit_check, 1)
                unittest.TestCase('__init__').assertEquals(CheckA.hit_check, 1)
                CheckG.hit_check = CheckG.hit_check + 1
                return ''

        class CheckH(AbstractCheck):
            applicable_on = [EveryEntity]
            depends_on = [CheckD, CheckF, CheckG]
            hit_check = 0

            def __init__(self, entity_context):
                super(CheckH, self).__init__(entity_context)

            def do_check(self, entity):
                unittest.TestCase('__init__').assertEquals(CheckA.hit_check, 1)
                unittest.TestCase('__init__').assertEquals(CheckB.hit_check, 1)
                unittest.TestCase('__init__').assertEquals(CheckC.hit_check, 1)
                unittest.TestCase('__init__').assertEquals(CheckD.hit_check, 1)
                unittest.TestCase('__init__').assertEquals(CheckE.hit_check, 1)
                unittest.TestCase('__init__').assertEquals(CheckF.hit_check, 1)
                unittest.TestCase('__init__').assertEquals(CheckG.hit_check, 1)
                CheckH.hit_check = CheckH.hit_check + 1
                return ''

        engine = CheckEngine([CheckA, CheckB, CheckC, CheckD, CheckE, CheckF, CheckG, CheckH],
                             self.entity, self.default_global_context)
        with patch.object(CheckEngine, 'do_entity_check_and_fix',
                          wraps=engine.do_entity_check_and_fix) as do_entity_check_and_fix:
            results = engine.check_all()
            self.assertEqual(CheckA.hit_check, 1)
            self.assertEqual(CheckB.hit_check, 1)
            self.assertEqual(CheckC.hit_check, 1)
            self.assertEqual(CheckD.hit_check, 1)
            self.assertEqual(CheckE.hit_check, 1)
            self.assertEqual(CheckF.hit_check, 1)
            self.assertEqual(CheckG.hit_check, 1)
            self.assertEqual(CheckH.hit_check, 1)
            self.assertEqual(do_entity_check_and_fix.call_count, 8)
            self.assertEqual(len(results), 8)
            self.assertTrue(CheckA.__name__ in results)
            self.assertTrue(CheckB.__name__ in results)
            self.assertTrue(CheckC.__name__ in results)
            self.assertTrue(CheckD.__name__ in results)
            self.assertTrue(CheckE.__name__ in results)
            self.assertTrue(CheckF.__name__ in results)
            self.assertTrue(CheckG.__name__ in results)
            self.assertTrue(CheckH.__name__ in results)

            for result in results.values():
                self.assertEqual(len(result['messages']), 0)
                self.assertEqual(result['result'], Result.CHECKED_OK)

if __name__ == '__main__':
    unittest.main()
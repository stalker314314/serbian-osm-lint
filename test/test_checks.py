# -*- coding: utf-8 -*-

import unittest

from osmread import Node

from checks import NameMissingCheck, NameCyrillicCheck, LatinNameExistsCheck, LatinNameSameAsCyrillicCheck
from checks import LatinNameNotInCyrillicCheck


class AbstractTestCheck(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(AbstractTestCheck, self).__init__(*args, **kwargs)
        self.global_context = {'fix': False, 'map': 'Serbia', 'dry_run': True}
        self.default_context = {'global_context': self.global_context}


class TestNameMissingCheck(AbstractTestCheck):
    def __init__(self, *args, **kwargs):
        super(TestNameMissingCheck, self).__init__(*args, **kwargs)

    def test_name_missing_check(self):
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        # If name does not exists, it is error
        self.assertTrue(NameMissingCheck(self.default_context).do_check(node) != '')
        # If name exists, but is None, it is error
        node.tags['name'] = None
        self.assertTrue(NameMissingCheck(self.default_context).do_check(node) != '')
        # If name exists, but is empty, it is error
        node.tags['name'] = ''
        self.assertTrue(NameMissingCheck(self.default_context).do_check(node) != '')
        # Name exists, no error
        node.tags['name'] = 'foo'
        self.assertTrue(NameMissingCheck(self.default_context).do_check(node) == '')


class TestNameCyrillicCheck(AbstractTestCheck):
    def __init__(self, *args, **kwargs):
        super(TestNameCyrillicCheck, self).__init__(*args, **kwargs)

    def test_name_cyrillic_check_serbia(self):
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        # If name does not exists, is None or empty, it is not error (name exists check will catch this)
        self.assertTrue(NameCyrillicCheck(self.default_context).do_check(node) == '')
        node.tags['name'] = None
        self.assertTrue(NameCyrillicCheck(self.default_context).do_check(node) == '')
        node.tags['name'] = ''
        self.assertTrue(NameCyrillicCheck(self.default_context).do_check(node) == '')
        # If name is not cyrillic, fail
        node.tags['name'] = 'foo'
        self.assertTrue(NameCyrillicCheck(self.default_context).do_check(node) != '')
        # If name is cyrillic, do not fail
        node.tags['name'] = 'фоо'
        self.assertTrue(NameCyrillicCheck(self.default_context).do_check(node) == '')

    def test_name_cyrillic_check_other_country(self):
        context = self.default_context.copy()
        context['global_context']['map'] = 'Atlantida'
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        # If name does not exists, is None or empty, it is not error (name exists check will catch this)
        self.assertTrue(NameCyrillicCheck(context).do_check(node) == '')
        node.tags['name:sr'] = None
        self.assertTrue(NameCyrillicCheck(context).do_check(node) == '')
        node.tags['name:sr'] = ''
        self.assertTrue(NameCyrillicCheck(context).do_check(node) == '')
        # If name is not cyrillic, fail
        node.tags['name:sr'] = 'foo'
        self.assertTrue(NameCyrillicCheck(context).do_check(node) != '')
        # If name is cyrillic, do not fail
        node.tags['name:sr'] = 'фоо'
        self.assertTrue(NameCyrillicCheck(context).do_check(node) == '')


class TestLatinNameExistsCheck(AbstractTestCheck):
    def __init__(self, *args, **kwargs):
        super(TestLatinNameExistsCheck, self).__init__(*args, **kwargs)

    def test_latin_name_missing_check_serbia(self):
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        # If name does not exists, it is error
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) != '')
        # If name exists, but is None, it is error
        node.tags['name:sr-Latn'] = None
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) != '')
        # If name exists, but is empty, it is error
        node.tags['name:sr-Latn'] = ''
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) != '')
        # Name exists, no error
        node.tags['name:sr-Latn'] = 'foo'
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) == '')
        # Name exists in cyrillic, no error (because this is not what this check checks)
        node.tags['name:sr-Latn'] = 'фоо'
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) == '')

    def test_latin_name_missing_check_other_country_no_sr_name(self):
        context = self.default_context.copy()
        context['global_context']['map'] = 'Atlantida'
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        # If name does not exists, but there is no name:sr, it is not error
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) == '')
        # If name exists, is None, but there is no name:sr, it is not error
        node.tags['name:sr-Latn'] = None
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) == '')
        # If name exists, is empty, but there is no name:sr, it is not error
        node.tags['name:sr-Latn'] = ''
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) == '')
        # Name exists, no error
        node.tags['name:sr-Latn'] = 'foo'
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) == '')
        # Name exists in cyrillic, no error (because this is not what this check checks)
        node.tags['name:sr-Latn'] = 'фоо'
        self.assertTrue(LatinNameExistsCheck(self.default_context).do_check(node) == '')

    def test_latin_name_missing_check_other_country_with_sr_name(self):
        context = self.default_context.copy()
        context['global_context']['map'] = 'Atlantida'
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        node.tags['name:sr'] = 'фоо'
        # If name does not exists, it is error
        self.assertTrue(LatinNameExistsCheck(context).do_check(node) != '')
        # If name exists, but is None, it is error
        node.tags['name:sr-Latn'] = None
        self.assertTrue(LatinNameExistsCheck(context).do_check(node) != '')
        # If name exists, but is empty, it is error
        node.tags['name:sr-Latn'] = ''
        self.assertTrue(LatinNameExistsCheck(context).do_check(node) != '')
        # Name exists, no error
        node.tags['name:sr-Latn'] = 'foo'
        self.assertTrue(LatinNameExistsCheck(context).do_check(node) == '')
        # Name exists in cyrillic, no error (because this is not what this check checks)
        node.tags['name:sr-Latn'] = 'фоо'
        self.assertTrue(LatinNameExistsCheck(context).do_check(node) == '')


class TestLatinNameSameAsCyrillicCheck(AbstractTestCheck):
    def __init__(self, *args, **kwargs):
        super(TestLatinNameSameAsCyrillicCheck, self).__init__(*args, **kwargs)

    def test_latin_name_same_as_cyrillic_check_serbia(self):
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        node.tags['name'] = 'фоо'
        node.tags['name:sr-Latn'] = 'foo'
        self.assertTrue(LatinNameSameAsCyrillicCheck(self.default_context).do_check(node) == '')
        node.tags['name:sr-Latn'] = 'foo2'
        self.assertTrue(LatinNameSameAsCyrillicCheck(self.default_context).do_check(node) != '')

    def test_latin_name_same_as_cyrillic_check_other_country(self):
        context = self.default_context.copy()
        context['global_context']['map'] = 'Atlantida'
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        node.tags['name:sr'] = 'фоо'
        node.tags['name:sr-Latn'] = 'foo'
        self.assertTrue(LatinNameSameAsCyrillicCheck(context).do_check(node) == '')
        node.tags['name:sr-Latn'] = 'foo2'
        self.assertTrue(LatinNameSameAsCyrillicCheck(context).do_check(node) != '')


class TestLatinNameNotInCyrillicCheck(AbstractTestCheck):
    def __init__(self, *args, **kwargs):
        super(TestLatinNameNotInCyrillicCheck, self).__init__(*args, **kwargs)

    def test_latin_name_not_in_cyrillic_check(self):
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        node.tags['name'] = 'бар'
        self.assertTrue(LatinNameNotInCyrillicCheck(self.default_context).do_check(node) == '')
        node.tags['name:sr-Latn'] = ''
        self.assertTrue(LatinNameNotInCyrillicCheck(self.default_context).do_check(node) == '')
        node.tags['name:sr-Latn'] = 'foo'
        self.assertTrue(LatinNameNotInCyrillicCheck(self.default_context).do_check(node) == '')
        node.tags['name:sr-Latn'] = 'фоо'
        self.assertTrue(LatinNameNotInCyrillicCheck(self.default_context).do_check(node) != '')
        # If there is no name, this check reports OK
        del node.tags['name']
        self.assertTrue(LatinNameNotInCyrillicCheck(self.default_context).do_check(node) == '')


if __name__ == '__main__':
    unittest.main()

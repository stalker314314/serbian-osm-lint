# -*- coding: utf-8 -*-

import unittest

from osmread import Way, Node, Relation

from applicability import City


class TestApplicability(unittest.TestCase):

    def test_city_way(self):
        self.assertFalse(City().is_entity_applicable(None))
        self.assertFalse(City().is_entity_applicable({}))
        way = Way(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, nodes=[])
        self.assertFalse(City().is_entity_applicable(way))
        way.tags['place'] = 'foo'
        self.assertFalse(City().is_entity_applicable(way))
        way.tags['place'] = 'city'
        self.assertTrue(City().is_entity_applicable(way))

    def test_city_node(self):
        node = Node(id=123, version=1, changeset=1, timestamp=None, uid=1, tags={}, lon=None, lat=None)
        self.assertFalse(City().is_entity_applicable(node))
        node.tags['place'] = 'foo'
        self.assertFalse(City().is_entity_applicable(node))
        node.tags['place'] = 'CiTy'
        self.assertFalse(City().is_entity_applicable(node))
        node.tags['place'] = 'city'
        self.assertTrue(City().is_entity_applicable(node))

if __name__ == '__main__':
    unittest.main()
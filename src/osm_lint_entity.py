# -*- coding: utf-8 -*-

import re

p_point = re.compile('Point\((?P<lat>[-0-9.]+)\s(?P<lon>[-0-9.]+)\)')
p_url = re.compile('https://www.openstreetmap.org/(?P<type>.*)/(?P<id>\d+)')


class OsmLintEntity(object):
    """
    Since our entities can either be of various types (PyOsmium, osmread...), this is wrapper to abstract those types.
    """

    def __init__(self, entity):
        if isinstance(entity, dict):
            self._convert_from_sophox(entity)
            return

        self.id = entity.id
        self.lat, self.lon = 0, 0
        self.origin = 'pbf'

        if isinstance(entity.tags, dict):
            self.tags = entity.tags
            self.lat = entity.lat
            self.lon = entity.lon

        else:
            self.lat = entity.location.lat
            self.lon = entity.location.lon
            self.tags = {}
            for tag in entity.tags:
                self.tags[tag.k] = tag.v
        self.entity_type = self._get_entity_type(entity)

    def _convert_from_sophox(self, entity):
        url = entity['id']['value']
        m = p_url.match(url)
        if not m:
            raise Exception('Unexpected URL for entity. It was {}', url)
        self.id = int(m.group('id'))
        self.entity_type = m.group('type')

        loc = entity['loc']['value']
        m = p_point.match(loc)
        if not m:
            raise Exception('Invalid format for point. Expected Point(lat lon) and got {}', loc)
        self.lat = float(m.group('lat'))
        self.lon = float(m.group('lon'))
        self.origin = 'sophox'
        self.tags = {}
        for key in entity:
            if key in ('id', 'loc'):  # Skip these special ones
                continue
            self.tags[key] = entity[key]

    @staticmethod
    def _get_entity_type(entity):
        """
        Helper method to get type of the entity.
        :param entity: Entity to get type from
        :return: Type of the entity. Can be one of the 'node', 'way', 'relation'
        """
        try:
            import osmread
            if isinstance(entity, osmread.Node):
                return 'node'
            elif isinstance(entity, osmread.Way):
                return 'way'
            elif isinstance(entity, osmread.Relation):
                return 'relation'
        except ImportError:
            pass
        try:
            import osmium
            if isinstance(entity, osmium.osm.Node):
                return 'node'
            elif isinstance(entity, osmium.osm.Way):
                return 'way'
            elif isinstance(entity, osmium.osm.Relation):
                return 'relation'
        except ImportError:
            pass
        raise Exception('Entity is neither PyOsmium not osmread known type'.format(entity))

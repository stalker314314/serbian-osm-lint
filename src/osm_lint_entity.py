# -*- coding: utf-8 -*-


class OsmLintEntity(object):
    """
    Since our entities can either be of PyOsmium or osmread types, this is wrapper to abstract those types.
    It is mostly like osmread's type, except it has "entity_type" attribute.
    """

    def __init__(self, entity):
        self.id = entity.id

        if isinstance(entity.tags, dict):
            self.tags = entity.tags
            self.lat, self.lon = 0, 0
            try:
                self.lat = entity.lat
                self.lon = entity.lon
            except AttributeError:
                # Ignore if it is not there
                pass
        else:
            self.lat = entity.location.lat
            self.lon = entity.location.lon
            self.tags = {}
            for tag in entity.tags:
                self.tags[tag.k] = tag.v
        self.entity_type = self._get_entity_type(entity)

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

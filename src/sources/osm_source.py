# -*- coding: utf-8 -*-

import tools
from osm_lint_entity import OsmLintEntity

logger = tools.get_logger(__name__)


class OSMSource(object):
    """
    Abstract OSM source that can retrieve OSM entities
    """
    def __init__(self, context, map_name, process_entity_callback):
        self.context = context
        self.map_name = map_name
        self.process_entity_callback = process_entity_callback
        self.processed = 0
        self.all_checks = {}

    def process_map(self):
        self._process_map()
        return self.all_checks

    def _process_map(self):
        raise NotImplemented()

    def _entity_found(self, raw_entity):
        self.processed += 1
        if self.processed % 100000 == 0:
            logger.info('[%s] Processed %d entities', self.map_name, self.processed)
            # If needed, this is how you can stop execution early
            # return all_checks
        try:
            entity = OsmLintEntity(raw_entity)
        except AttributeError as e:
            # We cannot process this entity, skip it
            logger.info(e)
            return

        checks_done = self.process_entity_callback(entity, self.context)
        if len(checks_done) > 0:
            if self.context['map'] == 'Serbia':
                name = entity.tags['name'] if 'name' in entity.tags else entity.id
            else:
                original_name = entity.tags['name'] if 'name' in entity.tags else entity.id
                if 'name:sr' in entity.tags:
                    name = '{0} / {1}'.format(original_name, entity.tags['name:sr'])
                else:
                    name = original_name
            self.all_checks[entity.id] = (name, entity.entity_type, checks_done)

# -*- coding: utf-8 -*-

"""
Module holding additional checks that others might find useful, but not part of standard check suite.
"""

from checks import AbstractCheck
from applicability import City, Town, Village


class RemoveLatinName(AbstractCheck):
    """
    Checks that looks for name:sr-Latn tag and removes them if it exists. Not part of standard suite.
    """
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['!Serbia']
    is_fixable = True
    explanation = 'Removes name:sr-Latn tag'

    def __init__(self, entity_context):
        super(RemoveLatinName, self).__init__(entity_context)

    def do_check(self, entity):
        if 'name:sr-Latn' in entity.tags and entity.tags['name:sr-Latn']:
            place_type = entity.tags['place'] if 'place' in entity.tags else '(unknown place type)'
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Latin name missing for {0} {1}'.format(place_type, name)
        return ''

    def fix(self, entity, api):
        name = entity.tags['name'] if self.map == 'Serbia' else entity.tags['name:sr']
        latin_name = entity.tags['name:sr-Latn']
        question = 'Are you sure you want to remove tag "name:sr-Latn" with value "{0}" from entity "{1}"'.format(
            latin_name, name
        )

        if entity.entity_type == 'way':
            way = api.WayGet(entity.id)
            if 'name:sr-Latn' in way['tag']:
                if self.ask_confirmation(question, entity):
                    del way['tag']['name:sr-Latn']
                    if not self.dry_run:
                        api.WayUpdate(way)
                    return 'name:sr-Latn for way {0} existed, removed it'.format(name, latin_name)
        elif entity.entity_type == 'node':
            node = api.NodeGet(entity.id)
            if 'name:sr-Latn' in node['tag']:
                if self.ask_confirmation(question, entity):
                    del node['tag']['name:sr-Latn']
                    if not self.dry_run:
                        api.NodeUpdate(node)
                    return 'name:sr-Latn for way {0} existed, removed it'.format(name, latin_name)
        return ''

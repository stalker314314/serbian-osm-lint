# -*- coding: utf-8 -*-

from sources.pbf_source import PBFSource
from sources.sophox_source import SophoxSource

class SourceFactory(object):
    """
    Based on info in configuration, creates appropriate source
    """
    def __init__(self, process_entity_callback, context):
        self.process_entity_callback = process_entity_callback
        self.context = context

    def create_source(self, map_name):
        location = self.context['maps'][map_name]['location']
        if location.endswith(".pbf"):
            return PBFSource(self.context, self.process_entity_callback, map_name, location)
        elif location.endswith(".sparql"):
            query = None
            with open(location, 'r', encoding='utf-8') as f:
                query = f.read()
            return SophoxSource(self.context, self.process_entity_callback, map_name, query)
        else:
            raise Exception("Unknown source")
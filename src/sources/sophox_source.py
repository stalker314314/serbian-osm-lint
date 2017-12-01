# -*- coding: utf-8 -*-

from SPARQLWrapper import SPARQLWrapper, JSON
import tools
from sources.osm_source import OSMSource
from osm_lint_entity import OsmLintEntity

logger = tools.get_logger(__name__)


class SophoxSource(OSMSource):
    def __init__(self, context, process_entity_callback, map_name, query):
        super(SophoxSource, self).__init__(context, map_name, process_entity_callback)
        self.query = query

    def _process_map(self):
        sparql = SPARQLWrapper("https://sophox.org/bigdata/namespace/wdq/sparql")
        sparql.setQuery(self.query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()

        if 'id' not in results['head']['vars']:
            raise Exception('Column "id" must be present in SPARQL query')
        if 'loc' not in results['head']['vars']:
            raise Exception('Column "loc" must be present in SPARQL query')

        # Count suggestions as total number of 'tag_N' columns. They should start from 1.
        # It is OK if there is no suggestions
        total_suggestions = 0
        while True:
            if 'tag_{0}'.format(total_suggestions + 1) in results['head']['vars']:
                total_suggestions = total_suggestions + 1
                if 'val_{0}'.format(total_suggestions) not in results['head']['vars']:
                    raise Exception('There exists "tag_{0}" column in SPARQL query and there is no "val_{0}" column'
                                    .format(total_suggestions))
            else:
                break

        all_checks = {}

        for result in results["results"]["bindings"]:
            #print(result)
            self._entity_found(result)

        return all_checks
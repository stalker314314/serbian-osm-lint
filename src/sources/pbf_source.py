# -*- coding: utf-8 -*-

from sources.osm_source import OSMSource
import tools
import os
import requests
import tempfile
from osm_lint_entity import OsmLintEntity

logger = tools.get_logger(__name__)


class PBFSource(OSMSource):
    """
    Source reading from .pbf file
    """
    def __init__(self, context, process_entity_callback, map_name, pbf_url):
        super(PBFSource, self).__init__(context, map_name, process_entity_callback)
        self.pbf_url = pbf_url

    def _download_map(self):
        """
        Downloads map from internet. It is up to the caller to remove this temporary file.
        :param map_name: Name of the map to download
        :param map_uri: URI of the map to download
        :return: Temprorary filename where map is downloaded
        """
        logger.info('[%s] Downloading %s', self.map_name, self.pbf_url)
        r = requests.get(self.pbf_url, stream=True)
        if not r.ok:
            raise Exception(r.reason)
        f = tempfile.NamedTemporaryFile(suffix='.pbf', prefix=self.map_name + '_', delete=False)
        try:
            chunk_number = 0
            for chunk in r.iter_content(chunk_size=1024):
                f.write(chunk)
                chunk_number = chunk_number + 1
                if chunk_number % (10 * 1024) == 0:
                    logger.info('[%s] Downloaded %d MB', self.map_name, chunk_number / 1024)
            f.close()
            logger.info('[%s] Map %s downloaded, parsing it now', self.map_name, self.map_name)
            return f.name
        except Exception as e:
            logger.exception(e)
            os.remove(f.name)
            raise

    def _process_map(self):
        """
        Process PBF file. It will download map and use either PyOsmium/osmread to read map.
        It also cleans all downloaded maps.
        """
        found_osmium, found_osmread = False, False
        try:
            import osmium
            found_osmium = True
        except ImportError:
            pass
        try:
            import osmread
            found_osmread = True
        except ImportError:
            pass

        if found_osmium:
            logger.info('[%s] Found osmium library, using it', self.map_name)
        elif found_osmread:
            logger.warning('[%s] Found osmread library, but not osmium library. Reading of maps will be slower', self.map_name)
        else:
            logger.error('[%s] Didn\'t found any library for reading maps, quitting', self.map_name)
            return

        filename = self._download_map()
        try:
            if found_osmium:
                return self.map_name, self.process_map_with_osmium(filename)
            elif found_osmread:
                return self.map_name, self.process_map_with_osmread(filename)
            else:
                logger.error('[%s] Didn\'t found any library for reading maps, quitting', self.map_name)
        except Exception as e:
            logger.exception(e)
            raise
        finally:
            os.remove(filename)

    def process_map_with_osmread(self, filename):
        """
        Process one map given its filename, using osmread
        """
        # This import is here since user doesn't have to have it (optional)
        from osmread import parse_file

        for raw_entity in parse_file(filename):
            self._entity_found(self, raw_entity)


    def process_map_with_osmium(self, filename):
        """
        Process one map given its filename, using PyOsmium
        """
        # This import is here since user doesn't have to have it (optional)
        import osmium

        class SignalEndOfExecution(Exception):
            pass

        class SerbianOsmLintHandler(osmium.SimpleHandler):
            def __init__(self, entity_found_callback):
                osmium.SimpleHandler.__init__(self)
                self.entity_found_callback = entity_found_callback
                self.processed = 0
                self.all_checks = {}

            def process_entity(self, raw_entity, entity_type):
                self.entity_found_callback(raw_entity)

            def node(self, n):
                self.process_entity(n, 'node')

            def way(self, w):
                self.process_entity(w, 'way')

        sloh = SerbianOsmLintHandler(self._entity_found)
        try:
            sloh.apply_file(filename)
        except SignalEndOfExecution:
            pass
        return sloh.all_checks
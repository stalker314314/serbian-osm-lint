# -*- coding: utf-8 -*-

import checks
import osmapi

# List of all checks that Serbian OSM Lint will perform
_checks = [
    checks.NameMissingCheck,
    checks.NameCyrillicCheck,
    checks.LatinNameExistsCheck,
    checks.LatinNameSameAsCyrillicCheck,
    checks.LatinNameNotInCyrillicCheck,
    checks.WikipediaEntryExistsCheck,
    checks.WikipediaEntryIsInSerbianCheck,
    checks.WikipediaEntryValidCheck,
    checks.WikidataEntryExistsCheck,
    checks.WikidataEntryValidCheck,
    checks.WikipediaAndWikidataInSyncCheck
]

# List of all maps that Serbian OSM Lint will check (in the format "common name"-> URI)
_maps = {
    #'Austria': 'https://download.geofabrik.de/europe/austria-latest.osm.pbf',
    'Bosnia-Herzegovina': 'https://download.geofabrik.de/europe/bosnia-herzegovina-latest.osm.pbf',
    'Bulgaria': 'https://download.geofabrik.de/europe/bulgaria-latest.osm.pbf',
    'Croatia': 'https://download.geofabrik.de/europe/croatia-latest.osm.pbf',
    'Greece': 'https://download.geofabrik.de/europe/greece-latest.osm.pbf',
    'Serbia': 'https://download.geofabrik.de/europe/serbia-latest.osm.pbf',
    'Macedonia': 'https://download.geofabrik.de/europe/macedonia-latest.osm.pbf'
}

_dry_run = True  # Do we actually commit OSM edits, or just change, but don't commit

_api = osmapi.OsmApi(username='branko@kokanovic.org', passwordfile='osm-password',
                     changesetauto=not _dry_run, changesetautosize=500, changesetautotags=
                     {u"comment": u"Serbian lint bot. Various fixes around wikidata/wikipedia links",
                      u"tag": u"mechanical=yes"})

global_context = {'checks': _checks,
                  'maps': _maps,
                  'report': True,
                  'fix': False,
                  'dry_run': _dry_run,
                  'api': _api,
                  'report_filename': 'report.html'}

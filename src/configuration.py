# -*- coding: utf-8 -*-

import os
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
    'Albania': 'https://download.geofabrik.de/europe/albania-latest.osm.pbf',
    'Andorra': 'https://download.geofabrik.de/europe/andorra-latest.osm.pbf',
    'Austria': 'https://download.geofabrik.de/europe/austria-latest.osm.pbf',
    'Belarus': 'https://download.geofabrik.de/europe/belarus-latest.osm.pbf',
    'Belgium': 'https://download.geofabrik.de/europe/belgium-latest.osm.pbf',
    'Bosnia-Herzegovina': 'https://download.geofabrik.de/europe/bosnia-herzegovina-latest.osm.pbf',
    'Bulgaria': 'https://download.geofabrik.de/europe/bulgaria-latest.osm.pbf',
    'Croatia': 'https://download.geofabrik.de/europe/croatia-latest.osm.pbf',
    'Greece': 'https://download.geofabrik.de/europe/greece-latest.osm.pbf',
    'Serbia': 'https://download.geofabrik.de/europe/serbia-latest.osm.pbf',
    'Macedonia': 'https://download.geofabrik.de/europe/macedonia-latest.osm.pbf'
}

_dry_run = True  # Do we actually commit OSM edits, or just change, but don't commit
_passwordfile='osm-password'

if not os.path.isfile(_passwordfile):
    error_msg = 'File {0} is missing. You need to create it and write in it <your_osm_mail>:<your_osm_password> for' \
                'Serbian OSM Lint to function.'.format(_passwordfile)
    print(error_msg)
    raise Exception(error_msg)

_api = osmapi.OsmApi(passwordfile=_passwordfile,
                     changesetauto=not _dry_run, changesetautosize=10, changesetautotags=
                     {u"comment": u"Serbian lint bot. Various fixes around name:sr, name:sr-Latn and"
                                  u"wikidata/wikipedia links",
                      u"tag": u"mechanical=yes"})

global_context = {'checks': _checks,
                  'maps': _maps,
                  'report': True,
                  'fix': False,
                  'dry_run': _dry_run,
                  'api': _api,
                  'report_filename': 'report.html'}

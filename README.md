Serbian OSM Lint
================

Serbian OSM Lint is a helper tool to detect and fix various issues on Serbian OSM project.
This is achieved by using "checks", where Serbian Lint checks are pre-made.
 
However, it is not constrained to just Serbian checks on OSM, it _is_ general purpose check framework for OSM!

It features:
* Support for Windows/Linux/Mac, Python 3.x
* Support for both (fast) [PyOsmium](http://osmcode.org/pyosmium/) library,
 as well as [osmread](https://github.com/dezhin/osmread) library (PyOsmium seems 2x-5x faster than osmread, but I dare you to compile it on Windows:)
* extensive configuration support
* support for both executing reports on checks and automated/semi-automated OSM editing
* fully tested and documented
* "check framework" where one can define checks by defining:
  * On which entity types check is applicable
  * On which maps check is applicable
  * Check and fix functions
  
  Serbian OSM Lint will then automatically resolve all dependencies and execute checks
and fixes on all entities from a given map.


Current results can be seen at:

http://kokanovic.org/serbian-osm-lint

If it is not updated for 3 days, contact me!

[This is OSM user](https://www.openstreetmap.org/user/Serbian%20OSM%20Lint%20bot)
that this script can be seen running live.
[Here](https://wiki.openstreetmap.org/wiki/Automated_edits/Serbian-OSM-Lint) is its OSM Wiki page too.


Usage
-----

You should have Python 3.x for Serbian OSM Lint to work.

1. Install requirements:

        sudo apt-get install build-essential libxml2-dev libxslt1-dev libboost-python-dev libbz2-dev libz-dev 
        pip install -r requirements.txt

_Note that if you are on Windows, you will not be able to install PyOSmium,
just remove it from requirements.txt, since Serbian OSM Lint has support for
fallback PBF reader._

2. Open src/configuration.py and adopt as necessary. Default configuration is for reporting.

3. From root directory, just run and you will get HTML report in `report.html` at the end:

        python src/main.py

    Running with fixing fixable LINT errors (but without actual committing to OSM),
and with report HTML outputted to foo.html:

        python src/main.py --fix --dry-run -o foo.html

    For list of all options, run with -h:

        python src/main.py -h

List of checks
--------------

Currently, there are dozens of checks. Here is brief overview of them:
* Checks that _name_ tag exists in entity
* Checks that _name_ tag is in cyrillic
* Checks that there is _sr:Latn_ tag and that it is transliterated from regular _name_ tag
* Checks that there are Wikipedia from Serbian Wikipedia and Wikidata entries
* Checks that Wikipedia and Wikidata entries match

Contributing
------------

Just go to issues and pick one:) If you can make report less uglier - please go for it:)

If you have idea for additional check(s), feel free to write it and I will surely add it! 

Tests
-----

Serbian OSM Lint is using nosetests. To execute all tests, go to root directory and run:

        nosetests
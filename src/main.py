# -*- coding: utf-8 -*-

import argparse
import collections
import datetime
import logging
import multiprocessing

# DO NOT REMOVE, needed to import it, so we can query __doc__ from those checks
import checks

_ = checks.AbstractCheck  # Just so lint is not complaining on unused import

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

import osmapi
import requests
import simplejson
from jinja2 import Environment, PackageLoader

import tools
from engine import CheckEngine, Result
from osm_lint_entity import OsmLintEntity

logger = tools.setup_logger(logging_level=logging.INFO)


def download_map(map_name, map_uri):
    """
    Downloads map from internet. It is up to the caller to remove this temporary file.
    :param map_name: Name of the map to download
    :param map_uri: URI of the map to download
    :return: Temprorary filename where map is downloaded
    """
    logger.info('[%s] Downloading %s', map_name, map_uri)
    r = requests.get(map_uri, stream=True)
    if not r.ok:
        raise Exception(r.reason)
    f = tempfile.NamedTemporaryFile(suffix='.pbf', prefix=map_name + '_', delete=False)
    try:
        chunk_number = 0
        for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)
            chunk_number = chunk_number + 1
            if chunk_number % (10 * 1024) == 0:
                logger.info('[%s] Downloaded %d MB', map_name, chunk_number / 1024)
        f.close()
        logger.info('[%s] Map %s downloaded, parsing it now', map_name, map_name)
        return f.name
    except Exception as e:
        logger.exception(e)
        os.remove(f.name)
        raise


def process_entity(entity, context):
    """
    Takes one entity and performs all check with engine on it.
    :param entity: Entity to check
    :param context: Context
    :return: List of all performed checks
    """
    cr = CheckEngine(context['checks'], entity, context)
    return cr.check_all()


def generate_report(context, all_checks):
    """
    Generates all data needed to create report and creates it.
    """
    env = Environment(loader=PackageLoader('__main__', 'templates'))
    template = env.get_template('report_template.html')

    # Calculate by countries and summary
    count_total_checks, count_total_errors, count_total_fixable_errors = 0, 0, 0
    countries = []
    for map_name, map_check in all_checks.items():
        count_map_checks = len(map_check)
        count_map_errors, count_map_fixable_errors = 0, 0
        for entity_check in map_check.values():
            for type_check in entity_check[2].values():
                if type_check['result'] == Result.CHECKED_ERROR:
                    count_map_errors = count_map_errors + 1
                    if type_check['fixable']:
                        count_map_fixable_errors = count_map_fixable_errors + 1
        countries.append((map_name, {'count_map_checks': count_map_checks,
                                     'count_map_errors': count_map_errors,
                                     'count_map_fixable_errors': count_map_fixable_errors}),)
        count_total_checks = count_total_checks + count_map_checks
        count_total_errors = count_total_errors + count_map_errors
        count_total_fixable_errors = count_total_fixable_errors + count_map_fixable_errors

    countries = sorted(countries, key=lambda country: country[0])
    summary = {
        'maps': len(all_checks),
        'count_total_checks': count_total_checks,
        'count_total_errors': count_total_errors,
        'count_total_fixable_errors': count_total_fixable_errors
    }

    # Calculate by check types
    check_types = {}
    for map_name, map_check in all_checks.items():
        for entity_check in map_check.values():
            for type_check, check in entity_check[2].items():
                if type_check not in check_types:
                    type_check_cls = eval('checks.' + type_check)
                    check_types[type_check] = {'explanation': type_check_cls.__doc__.strip(),
                                               'count_total_checks': 0,
                                               'count_total_errors': 0}
                check_types[type_check]['count_total_checks'] = check_types[type_check]['count_total_checks'] + 1
                if check['result'] != Result.CHECKED_OK:
                    check_types[type_check]['count_total_errors'] = check_types[type_check]['count_total_errors'] + 1

    check_types = collections.OrderedDict(sorted(check_types.items(), key=lambda c: c[0]))

    # Sort all checks by country (and sort all values which are also dictionaries by entity id)
    all_checks_sorted = {}
    for check, check_dict in all_checks.items():
        all_checks_sorted[check] = collections.OrderedDict(sorted(check_dict.items(), key=lambda c: c[0]))
    all_checks_sorted = collections.OrderedDict(sorted(all_checks_sorted.items(), key=lambda c: c[0]))

    output = template.render(d=datetime.datetime.now(), summary=summary, countries=countries, check_types=check_types,
                             all_checks=all_checks_sorted)
    with open(context['report_filename'], 'w', encoding='utf-8') as fh:
        fh.write(output)


def process_map(context, map_name):
    """
    Library agnostic map processing. It will download map and use either PyOsmium/osmread to read map.
    It also cleans all downloaded maps.
    """
    logger.info('[%s] Starting processing of map %s', map_name, map_name)

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
        logger.info('[%s] Found osmium library, using it', map_name)
    elif found_osmread:
        logger.warning('[%s] Found osmread library, but not osmium library. Reading of maps will be slower', map_name)
    else:
        logger.error('[%s] Didn\'t found any library for reading maps, quitting', map_name)
        return

    context = context.copy()
    context['map'] = map_name
    filename = download_map(map_name, context['maps'][map_name])
    try:
        if found_osmium:
            return map_name, process_map_with_osmium(context, filename)
        elif found_osmread:
            return map_name, process_map_with_osmread(context, filename)
        else:
            logger.error('[%s] Didn\'t found any library for reading maps, quitting', map_name)
    except Exception as e:
        logger.exception(e)
        raise
    finally:
        os.remove(filename)


def process_map_with_osmread(context, filename):
    """
    Process one map given its filename, using osmread
    """
    # This import is here since user doesn't have to have it (optional)
    from osmread import parse_file

    processed = 0
    all_checks = {}
    for raw_entity in parse_file(filename):
        entity = OsmLintEntity(raw_entity)
        processed += 1
        if processed % 100000 == 0:
            logger.info('[%s] Processed %d entities', context['map'], processed)
            # If needed, this is how you can stop execution early
            # return all_checks

        checks_done = process_entity(entity, context)

        if len(checks_done) > 0:
            if context['map'] == 'Serbia':
                name = entity.tags['name'] if 'name' in entity.tags else entity.id
            else:
                original_name = entity.tags['name'] if 'name' in entity.tags else entity.id
                if 'name:sr' in entity.tags:
                    name = '{0} / {1}'.format(original_name, entity.tags['name:sr'])
                else:
                    name = original_name
            all_checks[entity.id] = (name, entity.entity_type, checks_done)
    return all_checks


def process_map_with_osmium(context, filename):
    """
    Process one map given its filename, using PyOsmium
    """
    # This import is here since user doesn't have to have it (optional)
    import osmium

    class SignalEndOfExecution(Exception):
        pass

    class SerbianOsmLintHandler(osmium.SimpleHandler):
        def __init__(self, context):
            osmium.SimpleHandler.__init__(self)
            self.context = context
            self.processed = 0
            self.all_checks = {}

        def process_entity(self, raw_entity, entity_type):
            entity = OsmLintEntity(raw_entity)
            self.processed += 1
            if self.processed % 100000 == 0:
                logger.info('[%s] Processed %d entities', context['map'], self.processed)
                # If needed, this is how you can stop execution early
                # raise SignalEndOfExecution
            checks_done = process_entity(entity, self.context)

            if len(checks_done) > 0:
                if context['map'] == 'Serbia':
                    name = entity.tags['name'] if 'name' in entity.tags else entity.id
                else:
                    original_name = entity.tags['name'] if 'name' in entity.tags else entity.id
                    if 'name:sr' in entity.tags:
                        name = '{0} / {1}'.format(original_name, entity.tags['name:sr'])
                    else:
                        name = original_name
                self.all_checks[entity.id] = (name, entity_type, checks_done)

        def node(self, n):
            self.process_entity(n, 'node')

        def way(self, w):
            self.process_entity(w, 'way')

    sloh = SerbianOsmLintHandler(context)
    try:
        sloh.apply_file(filename)
    except SignalEndOfExecution:
        pass
    return sloh.all_checks


def create_global_context():
    parser = argparse.ArgumentParser(
        description='Serbian OSM Lint - helper tool to detect and fix various issues on Serbian OSM project ')
    parser.add_argument('--output-file', default='report.html',
                        help='Name of output HTML file. Default value is "report.html"')
    parser.add_argument('--maps-file', default='maps.json',
                        help='Name of file containing maps in JSON format. Default value is "maps.json"')
    parser.add_argument('--checks-file', default='checks.json',
                        help='Name of file containing checks in JSON format. Default value is "checks.json"')
    parser.add_argument('-f', '--fix', action='store_true',
                        help='Run in fixing/interactive mode. '
                             'Program will be run with one thread only and will ask for confirmations')
    parser.add_argument('--password-file', default='osm-password',
                        help='Filename of the file containing username and password for OSM.'
                             'Should contain one line in format: '
                             '<your_osm_mail>:<password>. Default value is "osm-password"')
    parser.add_argument('--changeset-size', metavar='N', default=20,
                        help='Number of changes in OSM after they are submitted to OSM. Default is 20.')
    parser.add_argument('-nr', '--no-report', action='store_true',
                        help='Do not create final HTML report. Default is to create report.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Dry run mode. Do all the checks and get data, but never commit to OSM')
    parser.add_argument('-v', '--version', action='version', version='Serbian OSM Lint 0.1')

    args = parser.parse_args()

    if not os.path.isfile(args.password_file):
        error_msg = 'File {0} is missing. You need to create it and write in it <your_osm_mail>:<your_osm_password> '\
                    'for Serbian OSM Lint to function.'.format(args.password_file)
        parser.error(error_msg)

    if not os.path.isfile(args.maps_file):
        error_msg = 'File with maps {0} is missing. You need to specify JSON file where maps are'.format(
            args.maps_file)
        parser.error(error_msg)
    with open(args.maps_file) as f:
        try:
            maps = simplejson.load(f)
        except Exception as e:
            parser.error('Error during parsing of {}: \n{}'.format(args.maps_file, e))

    if not os.path.isfile(args.checks_file):
        error_msg = 'File with checks {0} is missing. You need to specify JSON file where checks are'.format(
            args.checks_file)
        parser.error(error_msg)
    with open(args.checks_file) as f:
        try:
            checks_str = simplejson.load(f)
            all_checks = []
            for check_str in checks_str:
                all_checks.append(eval(check_str))
        except Exception as e:
            parser.error('Error during parsing of {}: \n{}'.format(args.checks_file, e))

    try:
        changeset_size = int(args.changeset_size)
    except ValueError:
        parser.error('--changeset_size must be integer')

    if changeset_size <= 0:
        parser.error('--changeset_size must be greater than 0')

    api = osmapi.OsmApi(passwordfile=args.password_file,
                        changesetauto=not args.dry_run, changesetautosize=changeset_size, changesetautotags=
                        {u"comment": u"Serbian lint bot. Various fixes around name:sr, name:sr-Latn and "
                                     u"wikidata/wikipedia links",
                         u"tag": u"mechanical=yes"})

    global_context = {'checks': all_checks,
                      'maps': maps,
                      'report': not args.no_report,
                      'fix': args.fix,
                      'dry_run': args.dry_run,
                      'api': api,
                      'report_filename': args.output_file}
    return global_context


def main():
    global_context = create_global_context()

    all_futures = []
    thread_count = 1 if global_context['fix'] else multiprocessing.cpu_count()
    thread_count = min(thread_count, len(global_context['maps']))
    logger.info('Using %d threads to do work', thread_count)

    # If we are fixing stuff, we cannot use ProcessPoolExecutor since threads are interacting with user
    executor_cls = ThreadPoolExecutor if global_context['fix'] else ProcessPoolExecutor
    with executor_cls(max_workers=thread_count) as executor:
        for map_name in global_context['maps']:
            future = executor.submit(process_map, global_context, map_name)
            all_futures.append(future)

        all_checks = {}
        for future in as_completed(all_futures):
            map_name, checks = future.result()
            all_checks[map_name] = checks

    if not global_context['dry_run']:
        global_context['api'].flush()
    if global_context['report']:
        generate_report(global_context, all_checks)

if __name__ == '__main__':
    main()

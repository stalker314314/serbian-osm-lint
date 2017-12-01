# -*- coding: utf-8 -*-

import argparse
import collections
import datetime
import logging
import multiprocessing

# DO NOT REMOVE, needed to import it, so we can query __doc__ from those checks
import checks, checks_extended

# Just so lint is not complaining on unused import
_ = checks.AbstractCheck
_ = checks_extended.AbstractCheck

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

import osmapi
import requests
import simplejson
from jinja2 import Environment, PackageLoader

import tools
from engine import CheckEngine, Result
from sources.source_factory import SourceFactory

logger = tools.setup_logger(logging_level=logging.INFO)


def process_entity(entity, context):
    """
    Takes one entity and performs all check with engine on it.
    :param entity: Entity to check
    :param context: Context
    :return: List of all performed checks
    """
    map_name = context['map']
    cr = CheckEngine(context['maps'][map_name]['checks'], entity, context)
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
                    type_check_cls = eval(type_check)
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


def create_global_context():
    parser = argparse.ArgumentParser(
        description='Serbian OSM Lint - helper tool to detect and fix various issues on Serbian OSM project ')
    parser.add_argument('--output-file', default='report.html',
                        help='Name of output HTML file. Default value is "report.html"')
    parser.add_argument('--config-file', default='config.json',
                        help='Name of file containing config in JSON format. Default value is "config.json"')
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

    if not os.path.isfile(args.config_file):
        error_msg = 'File with config {0} is missing. You need to specify JSON file where config is'.format(
            args.config_file)
        parser.error(error_msg)
    with open(args.config_file) as f:
        try:
            config = simplejson.load(f)
        except Exception as e:
            parser.error('Error during parsing of {}: \n{}'.format(args.config_file, e))
    # Replace checks in config with their eval-ulated version (helps to detects errors earlier)
    for map in config:
        eval_checks = []
        for check in config[map]['checks']:
            eval_checks.append(eval(check))
        config[map]['checks'] = eval_checks

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

    global_context = {'maps': config,
                      'report': not args.no_report,
                      'fix': args.fix,
                      'dry_run': args.dry_run,
                      'api': api,
                      'report_filename': args.output_file}
    return global_context


def process_map(context, map_name):
    """
    Figures out which source it should use and calls it
    """
    logger.info('[%s] Starting processing of map %s', map_name, map_name)
    context = context.copy()
    context['map'] = map_name
    source_factory = SourceFactory(process_entity, context)
    source = source_factory.create_source(map_name)
    return map_name, source.process_map()


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

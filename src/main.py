# -*- coding: utf-8 -*-

import datetime
import logging
import os
import tempfile

import requests
from jinja2 import Environment, PackageLoader

import tools
from configuration import global_context
from engine import CheckEngine, Result

logger = tools.setup_logger(logging_level=logging.INFO)


def download_map(map_name, map_uri):
    """
    Downloads map from internet. It is up to the caller to remove this temprorary file.
    :param map_name: Name of the map to download
    :param map_uri: URI of the map to download
    :return: Temprorary filename where map is downloaded
    """
    logger.info('Downloading %s', map_uri)
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
                logger.info('Downloaded %d MB', chunk_number / 1024)
        f.close()
        logger.info('Map %s downloaded, parsing it now', map_name)
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
    cr = CheckEngine(context['checks'], entity, global_context)
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
            for type_check in entity_check[1].values():
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
            for type_check, check in entity_check[1].items():
                if type_check not in check_types:
                    # DO NOT REMOVE, needed to import it, so we can query __doc__ from those checks
                    import checks # pylint: disable=unused-import
                    type_check_cls = eval('checks.' + type_check)
                    check_types[type_check] = {'explanation': type_check_cls.__doc__.strip(),
                                               'count_total_checks': 0,
                                               'count_total_errors': 0}
                check_types[type_check]['count_total_checks'] = check_types[type_check]['count_total_checks'] + 1
                if check['result'] != Result.CHECKED_OK:
                    check_types[type_check]['count_total_errors'] = check_types[type_check]['count_total_errors'] + 1

    output = template.render(d=datetime.datetime.now(), summary=summary, countries=countries, check_types=check_types,
                             all_checks=all_checks)
    with open(context['report_filename'], 'w', encoding='utf-8') as fh:
        fh.write(output)


def process_map(context):
    """
    Library agnostic map processing. It will download map and use either PyOsmium/osmread to read map.
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
        logger.info('Found osmium library, using it')
    elif found_osmread:
        logger.warning('Found osmread library, but not osmium library. Reading of maps will be slower')
    else:
        logger.error('Didn\'t found any library for reading maps, quitting')
        return

    map_name = context['map']
    filename = download_map(map_name, context['maps'][map_name])
    try:
        if found_osmium:
            return process_map_with_osmium(context, filename)
        elif found_osmread:
            return process_map_with_osmread(context, filename)
        else:
            logger.error('Didn\'t found any library for reading maps, quitting')
    except Exception as e:
        logger.exception(e)
        os.remove(filename)
        raise


def process_map_with_osmread(context, filename):
    """
    Process one map given its filename, using osmread
    """
    from osmread import parse_file, Way, Node

    processed = 0
    all_checks = {}
    for entity in parse_file(filename):
        processed += 1
        if processed % 100000 == 0:
            logger.info('Processed %d entities', processed)
            # If needed, this is how you can stop execution early
            return all_checks
        checks = process_entity(entity, context)

        entity_type = None
        if isinstance(entity, Way):
            entity_type = 'way'
        elif isinstance(entity, Node):
            entity_type = 'node'

        if len(checks) > 0:
            if context['map'] == 'Serbia':
                name = entity.tags['name'] if 'name' in entity.tags else entity.id
            else:
                original_name = entity.tags['name'] if 'name' in entity.tags else entity.id
                if 'name:sr' in entity.tags:
                    name = '{0} / {1}'.format(original_name, entity.tags['name:sr'])
                else:
                    name = original_name
            all_checks[entity.id] = (name, entity_type, checks)
    return all_checks


def process_map_with_osmium(context, filename):
    """
    Process one map given its filename, using PyOsmium
    """
    import osmium # This import is here since user doesn't have to have it

    class SignalEndOfExecution(Exception):
        pass

    class SerbianOsmLintHandler(osmium.SimpleHandler):
        def __init__(self, context):
            osmium.SimpleHandler.__init__(self)
            self.context = context
            self.processed = 0
            self.all_checks = {}

        def process_entity(self, entity, entity_type):
            self.processed += 1
            if self.processed % 100000 == 0:
                logger.info('Processed %d entities', self.processed)
                # If needed, this is how you can stop execution early
                # raise SignalEndOfExecution
            checks = process_entity(entity, self.context)

            if len(checks) > 0:
                if context['map'] == 'Serbia':
                    name = entity.tags['name'] if 'name' in entity.tags else entity.id
                else:
                    original_name = entity.tags['name'] if 'name' in entity.tags else entity.id
                    if 'name:sr' in entity.tags:
                        name = '{0} / {1}'.format(original_name, entity.tags['name:sr'])
                    else:
                        name = original_name
                self.all_checks[entity.id] = (name, entity_type, checks)

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


def main():
    all_checks = {}
    for map_name in global_context['maps']:
        logger.info('Processing map %s', map_name)
        global_context['map'] = map_name
        checks = process_map(global_context)
        all_checks[map_name] = checks
    if not global_context['dry_run']:
        global_context['api'].flush()
    if global_context['report']:
        generate_report(global_context, all_checks)

if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-

import pywikibot

import tools
from applicability import City, Town, Village
from exceptions import CalculateDistanceException
from haversine import haversine
from transliteration import at_least_some_in_cyrillic, cyr2lat

en_wiki = pywikibot.Site("en", "wikipedia")
sr_wiki = pywikibot.Site("sr", "wikipedia")
wikidata = pywikibot.Site("wikidata", "wikidata")
wiki_repo = wikidata.data_repository()

logger = tools.get_logger(__name__)


def _wiki_osm_distance(wikipedia_entry, valid_boxes, osm_entity):
    """
    Calculates distance between wiki entry and OSM entity,
    or throws CalculateDistanceException if it cannot calculate it.
    :param wikipedia_entry: Wikipedia entry to calculate distance
    :param valid_boxes: Template boxes from where latitude/longitude will be pulled from
    :param osm_entity: OSM entity
    :return: distance in km
    """
    templates = wikipedia_entry.raw_extracted_templates
    found_box = next((t[1] for t in templates if t[0] in valid_boxes), None)
    if found_box is None:
        raise CalculateDistanceException(
            'Cannot calculate distance as Wikipedia article {0} does not contain any of valid boxes {1}'.format(
                     wikipedia_entry.title, ','.join(valid_boxes)))

    if 'гшир' not in found_box or 'гдуж' not in found_box:
        raise CalculateDistanceException('Wikipedia entry {0} is missing latitude or longitude'.format(
            wikipedia_entry.title))

    wiki_point = (float(found_box['гшир']), float(found_box['гдуж']))

    osm_point = (osm_entity.lat, osm_entity.lon)
    distance = haversine(wiki_point, osm_point)
    return distance


def _guess_from_wikipedia(name, entity, api, valid_boxes, visited_pages=None, depth=1):
    """
    Try to get article from Serbian Wikipedia with given name and check if it is proper article for a given entity.
    Article needs to fulfil couple of criterias:
    * It needs to exist:)
    * It needs to have at least one of the valid_boxes template (template that each place in Serbia have)
    * Template mentioned above need to have latitude and longitude
    * Latitude and longitude should not differ more than 5km between OSM entity and template
    * If article is leading to ambiguous page (template 'Вишезначна одредница'), we will recursively check all
        links pointing to it.
    * If article is having 'other meaning' link, it will recursively check that link
    :param name: Name to check on wiki
    :param entity: Entity to get wikipedia link for
    :return: Full link name, or None if it is not guessed correctly
    """
    if visited_pages is None:
        visited_pages = []

    if name in visited_pages:
        # We already checked this page, bail out
        return None
    visited_pages.append(name)

    if depth > 3:
        # We are too much in recursion, bail out
        return None

    page = pywikibot.Page(sr_wiki, name)
    try:
        if page.pageid == 0:
            logger.debug('Wikipedia entry for %s does not exist', name)
            return None
    except pywikibot.exceptions.InvalidTitle as e:
        logger.exception(e)
        return None

    # Seems that there is a wikipedia entry by this name, let's see if it is about residential place
    templates = page.raw_extracted_templates
    found_box = next((t[1] for t in templates if t[0] in valid_boxes), None)
    if not found_box:
        ambiguous_page = next(
            (t[1] for t in templates if t[0].lower() == 'вишезначна одредница'), None)
        if ambiguous_page is None:
            other_meanings = [t[1] for t in templates if t[0].lower().startswith('друго значење')]
            if len(other_meanings) == 0:
                logger.debug('Wikipedia entry for %s is not entry for residential area', name)
                return None
            else:
                # There is page with more meanings, let's try there
                for other_meaning in other_meanings:
                    for l in other_meaning.values():
                        if l.startswith('[[') and l.endswith(']]'):
                            l = l[2:-2]
                        result = _guess_from_wikipedia(l, entity, api, valid_boxes, visited_pages, depth + 1)
                        if result:
                            return result
                        if '(вишезначна_одредница)' not in l:
                            result = _guess_from_wikipedia('{0} (вишезначна_одредница)'.format(l),
                                                           entity, api, valid_boxes, visited_pages, depth + 1)
                            if result:
                                return result
                    else:
                        result = _guess_from_wikipedia('{0} (вишезначна_одредница)'.format(name), entity, api,
                                                       valid_boxes, visited_pages, depth + 1)
                        if result:
                            return result
                return None
        else:
            # This is ambiguous page, let's try calling all links from there recursively
            logger.debug('Wikipedia entry %s is ambiguous page, going into pages it is linking to', name)
            for page in page.linkedPages():
                result = _guess_from_wikipedia(page.title(), entity, api, valid_boxes, visited_pages, depth + 1)
                if result:
                    return result
            return None

    # It is about residential place, let's see how apart are Wiki and OSM place,
    # if they are not too far apart (5km), it means we have a winner!
    try:
        distance = _wiki_osm_distance(page, valid_boxes, entity)
        if distance <= 5:
            return name
        else:
            entity_name = entity.tags['name'] if 'name' in entity.tags else entity.id
            logger.info('Wikipedia and OSM entries are more than 5km apart (%.2f km) for place %s.', distance, entity_name)
            return None
    except CalculateDistanceException as e:
        logger.debug(e.message)
        return None


class AbstractCheck(object):
    applicable_on = []
    is_fixable = False
    explanation = ''

    def __init__(self, entity_context):
        self.entity_context = entity_context
        # helpers to shorten getting stuff from global_context
        self.map = entity_context['global_context']['map']
        self.dry_run = entity_context['global_context']['dry_run']

    def do_check(self, entity):
        """
        Do check.
        :param entity: Entity on top to which to apply check. Engine guarantees entity is applicable for this check.
        Engine also guarantees that all dependent checks are satisfied prior to calling this check.
        :return: Empty string if check is successful. Non-empty if there is error with error message being returned.
        """
        return ''

    def fix(self, entity, api):
        """
        Returns empty string if fix is not done. Returns changeset comment if fix is applied.
        Since entities can be stale, implementor must ensure that fix is idempotent and that current version also needs
        fixing. Use osmapi to check and apply fix.
        Engine guarantees that there is open changeset.
        :param entity: Entity to fix. Engine guarantees entity is applicable for this check.
        Engine also guarantees that all dependent checks are satisfied prior to calling this check. If there is
        additional checks, you'll have to do them manually.
        :param api: OsmApi
        """
        return ''

    def ask_confirmation(self, input_text, entity):
        """
        Simple wrapper to ask user to do something. Method will append "(y/n)" and dump entity
        :param input_text: Text to ask. 
        :param entity: entity for whcih question is being asked
        :return: True if user confirmed, False otherwise
        """
        for k, v in entity.tags.items():
            print('{0}: {1}'.format(k, v))
        print('https://www.openstreetmap.org/{0}/{1}'.format(entity.entity_type, entity.id))
        response = input('[{0}] {1} (Y/n)?'.format(self.map, input_text))
        if response == '' or response.lower() == 'y':
            return True
        return False


class NameMissingCheck(AbstractCheck):
    """
    Checks that 'name' tag is present in entity.
    """
    applicable_on = [City, Town, Village]

    def __init__(self, entity_context):
        super(NameMissingCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'name' not in entity.tags or not entity.tags['name']:
            place_type = entity.tags['place'] if 'place' in entity.tags else '(unknown place type)'
            return 'Name missing for {0} with id {1}: {2}'.format(place_type, entity.id, entity)
        return ''


class NameCyrillicCheck(AbstractCheck):
    """
    Checks that name of the entity is in cyrillic script.
    """
    applicable_on = [City, Town, Village]

    def __init__(self, entity_context):
        super(NameCyrillicCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if self.map == 'Serbia' and 'name' in entity.tags and entity.tags['name']:
            # Exclude places close, but not in Serbia
            if 'is_in:country' in entity.tags and entity.tags['is_in:country'] != 'Serbia':
                return ''
            name = entity.tags['name']
        elif self.map != 'Serbia' and 'name:sr' in entity.tags and entity.tags['name:sr']:
            name = entity.tags['name:sr']
        else:
            return ''

        if not at_least_some_in_cyrillic(name):
            place_type = entity.tags['place'] if 'place' in entity.tags else '(unknown place type)'
            return 'Seems that {0} name is not in cyrillic for "{1}"'.format(place_type, name)
        return ''


class LatinNameExistsCheck(AbstractCheck):
    """
    Checks that for entity exists name in sr-Latn too.
    """
    applicable_on = [City, Town, Village]
    is_fixable = True

    def __init__(self, entity_context):
        super(LatinNameExistsCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if self.map == 'Serbia' and 'name:sr-Latn' in entity.tags and entity.tags['name:sr-Latn']:
            # Exclude places close, but not in Serbia
            if 'is_in:country' in entity.tags and entity.tags['is_in:country'] != 'Serbia':
                return ''
            return ''
        if self.map != 'Serbia' and 'name:sr-Latn' in entity.tags and entity.tags['name:sr-Latn']:
            return ''
        if self.map != 'Serbia' and 'name:sr' not in entity.tags:
            # If there is no name in cyrillic, no way we can deduce sr-Latn name. Let it alone, there
            # are other checks (for cyrillic name existance) that will catch this entity
            return ''

        place_type = entity.tags['place'] if 'place' in entity.tags else '(unknown place type)'
        name = entity.tags['name'] if 'name' in entity.tags else entity.id
        return 'Latin name missing for {0} {1}'.format(place_type, name)

    def fix(self, entity, api):
        if self.map == 'Serbia':
            if NameMissingCheck(self.entity_context).do_check(entity) != '':
                # We cannot automatically set latin name, if cyrillic is not set
                return ''
        else:
            if 'name:sr' not in entity.tags:
                return ''

        if NameCyrillicCheck(self.entity_context).do_check(entity) != '':
            # Doesn't make sense to set latin name, if original name is not in cyrillic
            return ''

        name = entity.tags['name'] if self.map == 'Serbia' else entity.tags['name:sr']
        latin_name = cyr2lat(name)
        question = 'Are you sure you want to append tag "name:sr-Latn" with value "{0}" to entity "{1}"'.format(
            latin_name, name
        )

        if entity.entity_type == 'way':
            way = api.WayGet(entity.id)
            if 'name:sr-Latn' not in way['tag']:
                if self.ask_confirmation(question, entity):
                    way['tag']['name:sr-Latn'] = latin_name
                    if not self.dry_run:
                        api.WayUpdate(way)
                    return 'name:sr-Latn for way {0} didn\'t exists, added it as "{1}"'.format(name, latin_name)
        elif entity.entity_type == 'node':
            node = api.NodeGet(entity.id)
            if 'name:sr-Latn' not in node['tag']:
                if self.ask_confirmation(question, entity):
                    node['tag']['name:sr-Latn'] = latin_name
                    if not self.dry_run:
                        api.NodeUpdate(node)
                    return 'name:sr-Latn for node {0} didn\'t exists, added it as "{1}"'.format(name, latin_name)
        return ''


class LatinNameSameAsCyrillicCheck(AbstractCheck):
    """
    If cyrillic name and sr-Latn name tags exists, checks that cyrillic name is transliterated equivalently to sr-Latn.
    """
    applicable_on = [City, Town, Village]
    is_fixable = True

    def __init__(self, entity_context):
        super(LatinNameSameAsCyrillicCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if self.map == 'Serbia' and 'name' not in entity.tags:
            return ''
        if self.map != 'Serbia' and 'name:sr' not in entity.tags:
            return ''
        if 'name:sr-Latn' not in entity.tags:
            return ''
        # Exclude places close, but not in Serbia
        if 'is_in:country' in entity.tags and entity.tags['is_in:country'] != 'Serbia':
            return ''

        latin_name = entity.tags['name:sr-Latn']
        cyrillic_name = entity.tags['name'] if self.map == 'Serbia' else entity.tags['name:sr']
        if cyr2lat(cyrillic_name) != latin_name:
            place_type = entity.tags['place'] if 'place' in entity.tags else '(unknown place type)'
            return 'Latin name {0} for {1} {2} is not properly transliterated'.format(
                latin_name, place_type, cyrillic_name)
        return ''

    def fix(self, entity, api):
        name = entity.tags['name'] if self.map == 'Serbia' else entity.tags['name:sr']
        old_latin_name = entity.tags['name:sr-Latn']
        correct_latin_name = cyr2lat(name)
        question = 'Latin name different than cyrillic name. Are you sure you want to change tag "name:sr-Latn" ' \
                   'for entity "{0}" with new value "{1}" (old value is "{2}") '.format(
                    name, correct_latin_name, old_latin_name
        )
        if entity.entity_type == 'way':
            way = api.WayGet(entity.id)
            online_name = way['tag']['name'] if self.map == 'Serbia' else way['tag']['name:sr']
            if 'name:sr-Latn' in way['tag'] and online_name == name and way['tag']['name:sr-Latn'] == old_latin_name:
                if self.ask_confirmation(question, entity):
                    way['tag']['name:sr-Latn'] = correct_latin_name
                    if not self.dry_run:
                        api.WayUpdate(way)
                    return 'name:sr-Latn for way {0} was different than in cyrillic, fixed it to be "{1}"'.format(
                        name, correct_latin_name)
        elif entity.entity_type == 'node':
            node = api.NodeGet(entity.id)
            online_name = node['tag']['name'] if self.map == 'Serbia' else node['tag']['name:sr']
            if 'name:sr-Latn' in node['tag'] and online_name == name and node['tag']['name:sr-Latn'] == old_latin_name:
                if self.ask_confirmation(question, entity):
                    node['tag']['name:sr-Latn'] = correct_latin_name
                    if not self.dry_run:
                        api.NodeUpdate(node)
                    return 'name:sr-Latn for node {0} was different than in cyrillic, fixed it to be "{1}"'.format(
                        name, correct_latin_name)
        return ''


class LatinNameNotInCyrillicCheck(AbstractCheck):
    """
    Check that sr-Latn name in tags is not in cyrillic script.
    """
    applicable_on = [City, Town, Village]

    def __init__(self, entity_context):
        super(LatinNameNotInCyrillicCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'name' not in entity.tags:
            return ''

        if 'name:sr-Latn' in entity.tags and at_least_some_in_cyrillic(entity.tags['name:sr-Latn']):
            place_type = entity.tags['place'] if 'place' in entity.tags else '(unknown place type)'
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'There is cyrillic in {0} name {1} for latin version {2}'.format(
                place_type, name, entity.tags['name:sr-Latn'])
        return ''


class WikipediaEntryExistsCheck(AbstractCheck):
    """
    Check that there exists Wikipedia entry for entity.
    """
    applicable_on = [City, Town, Village]
    is_fixable = True

    def __init__(self, entity_context):
        super(WikipediaEntryExistsCheck, self).__init__(entity_context)

    def do_check(self, entity):
        # Exclude places close, but not in Serbia
        if 'is_in:country' in entity.tags and entity.tags['is_in:country'] != 'Serbia':
            return ''

        if 'wikipedia' not in entity.tags:
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Wikipedia missing for {0} {1}'.format(place_type, name)
        return ''

    def fix(self, entity, api):
        if NameMissingCheck(self.entity_context).do_check(entity) != '':
            # We should not set Wikipedia tag, if there is no name
            return ''
        if NameCyrillicCheck(self.entity_context).do_check(entity) != '':
            # We should not set Wikipedia tag, if name is not in cyrillic
            return ''

        name = entity.tags['name'] if self.map == 'Serbia' else entity.tags['name:sr']
        guess_from_wiki = _guess_from_wikipedia(name, entity, api,
                                                ['Насељено место у Србији', 'Град у Србији', 'Градска четврт'])
        if guess_from_wiki:
            if entity.entity_type == 'way':
                osm_entity = api.WayGet(entity.id)
            else:
                osm_entity = api.NodeGet(entity.id)

            if 'wikipedia' not in osm_entity['tag']:
                wikipedia_tag = 'sr:{0}'.format(guess_from_wiki)
                question = 'Wikipedia entry missing, but page with most likelihood was found. ' \
                           'Are you sure you want to add tag "wikipedia" for entity "{0}" with value "{1}"'.format(
                            name, wikipedia_tag)
                if self.ask_confirmation(question, entity):
                    osm_entity['tag']['wikipedia'] = wikipedia_tag
                    if not self.dry_run:
                        if entity.entity_type == 'way':
                            api.WayUpdate(osm_entity)
                        else:
                            api.NodeUpdate(osm_entity)
                    return 'Wikipedia tag for {0} "{1}" is updated to be "{2}"'.format(
                        'way' if entity.entity_type == 'way' else 'node', name, wikipedia_tag)
        return ''


class WikipediaEntryIsInSerbianCheck(AbstractCheck):
    """
    Check that Wikipedia entry for entity is in local Wikipedia, e.g. Serbian.
    """
    applicable_on = [City, Town, Village]
    is_fixable = True

    def __init__(self, entity_context):
        super(WikipediaEntryIsInSerbianCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'wikipedia' not in entity.tags:
            return ''

        # Exclude places close, but not in Serbia
        if 'is_in:country' in entity.tags and entity.tags['is_in:country'] != 'Serbia':
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return ''

        if not entity.tags['wikipedia'].startswith('sr:'):
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Wikipedia entry is {0} and is not in Serbian for {1} {2}'.format(
                entity.tags['wikipedia'], place_type, name)
        return ''

    def fix(self, entity, api):
        """
        Basically, same fix as if there is no wikipedia entry, but we are not adding new tag, we replace existing one
        """
        if NameMissingCheck(self.entity_context).do_check(entity) != '':
            # We should not set Wikipedia tag, if there is no name
            return ''
        if NameCyrillicCheck(self.entity_context).do_check(entity) != '':
            # We should not set Wikipedia tag, if name is not in cyrillic
            return ''

        name = entity.tags['name'] if self.map == 'Serbia' else entity.tags['name:sr']
        guess_from_wiki = _guess_from_wikipedia(name, entity, api,
                                                ['Насељено место у Србији', 'Град у Србији', 'Градска четврт'])
        if guess_from_wiki:
            if entity.entity_type == 'way':
                osm_entity = api.WayGet(entity.id)
            else:
                osm_entity = api.NodeGet(entity.id)

            if 'wikipedia' in osm_entity['tag'] and not osm_entity['tag']['wikipedia'].startswith('sr:'):
                wikipedia_tag = 'sr:{0}'.format(guess_from_wiki)
                question = 'Wikipedia entry was not from Serbian wiki, but was "{0}". ' \
                           'Are you sure you want to replace tag "wikipedia" for entity "{1}" with value "{2}"'.format(
                            osm_entity['tag']['wikipedia'], name, wikipedia_tag)
                if self.ask_confirmation(question, entity):
                    osm_entity['tag']['wikipedia'] = wikipedia_tag
                    if not self.dry_run:
                        if entity.entity_type == 'way':
                            api.WayUpdate(osm_entity)
                        else:
                            api.NodeUpdate(osm_entity)
                    return 'Wikipedia tag for {0} "{1}" is updated to be "{2}"'.format(
                        'way' if entity.entity_type == 'way' else 'node', name, wikipedia_tag)
        return ''


class WikipediaEntryValidCheck(AbstractCheck):
    """
    Checks that Wikipedia entry for a given entity actually exists in Wikipedia.
    """
    applicable_on = [City, Town, Village]

    def __init__(self, entity_context):
        super(WikipediaEntryValidCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'name' not in entity.tags:
            return ''
        if 'wikipedia' not in entity.tags:
            return ''
        if not entity.tags['wikipedia'].startswith('sr:'):
            return ''

        # Exclude places close, but not in Serbia
        if 'is_in:country' in entity.tags and entity.tags['is_in:country'] != 'Serbia':
            return ''

        place_type = entity.tags['place']
        name = entity.tags['name'] if 'name' in entity.tags else entity.id

        wikipedia_entry = self.entity_context['local_store']['wikipedia']\
            if 'wikipedia' in self.entity_context['local_store'] else None

        if wikipedia_entry is not None:
            # Already checked, everything is OK
            return ''

        error_message = 'Wikipedia entry {0} is not valid for {1} {2}'.format(
            entity.tags['wikipedia'][3:], place_type, name)
        wikipedia_entry = pywikibot.Page(sr_wiki, entity.tags['wikipedia'][3:])
        try:
            if wikipedia_entry.pageid == 0:
                return error_message
        except pywikibot.exceptions.NoPage:
            return error_message

        try:
            distance = _wiki_osm_distance(wikipedia_entry,
                                          ['Насељено место у Србији', 'Град у Србији', 'Градска четврт'], entity)
            if distance <= 5:
                # Cache it now
                self.entity_context['local_store']['wikipedia'] = wikipedia_entry
                return ''
            else:
                entity_name = entity.tags['name'] if 'name' in entity.tags else entity.id
                return 'Wikipedia and OSM entries are more than 5km apart ({0:.2f} km) for place {1}.'.format(
                    distance, entity_name)
        except CalculateDistanceException as e:
            logger.debug(e.message)
            return e.message


class WikidataEntryExistsCheck(AbstractCheck):
    """
    Check that there exists Wikidata entry for entity. 
    """
    applicable_on = [City, Town, Village]
    is_fixable = True

    def __init__(self, entity_context):
        super(WikidataEntryExistsCheck, self).__init__(entity_context)

    def do_check(self, entity):
        # Exclude places close, but not in Serbia
        if 'is_in:country' in entity.tags and entity.tags['is_in:country'] != 'Serbia':
            return ''

        if 'wikidata' not in entity.tags:
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Wikidata missing for {0} {1}'.format(place_type, name)
        return ''

    def fix(self, entity, api):
        """
        Fixing is by going to wikipedia article and getting Q value from there
        """
        if WikipediaEntryValidCheck(self.entity_context).do_check(entity) != '':
            # If Wikipedia is not valid entry, no point getting wikidata
            return ''

        name = entity.tags['name'] if self.map == 'Serbia' else entity.tags['name:sr']
        wikipedia_entry = self.entity_context['local_store']['wikipedia'] \
            if 'wikipedia' in self.entity_context['local_store'] else None

        if wikipedia_entry:
            if entity.entity_type == 'way':
                osm_entity = api.WayGet(entity.id)
            else:
                osm_entity = api.NodeGet(entity.id)

            if 'wikidata' not in osm_entity['tag']:
                wikidata = wikipedia_entry.data_item().id
                question = 'Wikidata entry was missing and it exists (based on Wikipedia article "{0}"). ' \
                           'Are you sure you want to add tag "wikidata" for entity "{1}" with value "{2}"'.format(
                            osm_entity['tag']['wikipedia'], name, wikidata)
                if self.ask_confirmation(question, entity):
                    osm_entity['tag']['wikidata'] = wikidata
                    if not self.dry_run:
                        if entity.entity_type == 'way':
                            api.WayUpdate(osm_entity)
                        else:
                            api.NodeUpdate(osm_entity)
                    return 'Wikidata tag for {0} "{1}" is set to be "{2}"'.format(
                        'way' if entity.entity_type == 'way' else 'node', name, wikidata)
        return ''


class WikidataEntryValidCheck(AbstractCheck):
    """
    Checks that Wikidata entry for a given entity actually exists in Wikidata.
    """
    applicable_on = [City, Town, Village]

    def __init__(self, entity_context):
        super(WikidataEntryValidCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'wikidata' not in entity.tags:
            return ''

        if 'is_in:country' in entity.tags and entity.tags['is_in:country'] != 'Serbia':
            return ''

        wikidata_entry = pywikibot.ItemPage(wiki_repo, entity.tags['wikidata'])
        if wikidata_entry.pageid == 0:
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Wikidata entry {0} for {1} {2} wrong'.format(entity.tags['wikidata'], place_type, name)
        self.entity_context['local_store']['wikidata'] = wikidata_entry
        return ''


class WikipediaAndWikidataInSyncCheck(AbstractCheck):
    """
    If both Wikipedia and Wikidata entry do exist, checks that Wikidata entry links to Wikipedia entry.
    """
    applicable_on = [City, Town, Village]

    def __init__(self, entity_context):
        super(WikipediaAndWikidataInSyncCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'wikipedia' not in entity.tags:
            return ''

        if 'wikidata' not in entity.tags:
            return ''

        if 'is_in:country' in entity.tags and entity.tags['is_in:country'] != 'Serbia':
            return ''

        wikidata_entry = self.entity_context['local_store']['wikidata']
        wd_txt = wikidata_entry.text
        if 'labels' in wd_txt and 'sr' in wd_txt['labels'] and wd_txt['labels']['sr'] != entity.tags['wikipedia'][3:]:
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Wikidata entry {0} for {1} {2} doesn\'t match wikipedia entry ({3})for it'.format(
                entity.tags['wikidata'], place_type, name, entity.tags['wikipedia'])
        return ''


class IsInCountryCheck(AbstractCheck):
    """
    Checks that there exists "is_in:country" tag
    """
    applicable_on = [City, Town, Village]
    is_fixable = True

    def __init__(self, entity_context):
        super(IsInCountryCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'is_in:country' not in entity.tags:
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'is_in:country missing for {0} {1}'.format(place_type, name)
        return ''

    def fix(self, entity, api):
        name = entity.tags['name'] if 'name' in entity.tags else entity.id
        latin_name = cyr2lat(name)
        if entity.entity_type == 'way':
            way = api.WayGet(entity.id)
            if 'is_in:country' not in way['tag']:
                way['tag']['is_in:country'] = 'Serbia'
                if not self.dry_run:
                    api.WayUpdate(way)
                return 'is_in:country for way {0} was missing, added it to be "{1}"'.format(name, 'Serbia')
        if entity.entity_type == 'node':
            node = api.NodeGet(entity.id)
            if 'is_in:country' not in node['tag']:
                node['tag']['is_in:country'] = 'Serbia'
                if not self.dry_run:
                    api.NodeUpdate(node)
                return 'is_in:country for node {0} was missing, added it to be "{1}"'.format(name, 'Serbia')
        return ''

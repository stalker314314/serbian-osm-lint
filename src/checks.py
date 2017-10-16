# -*- coding: utf-8 -*-

import pywikibot
import tools
from applicability import City, Town, Village

from transliteration import at_least_some_in_cyrillic, cyr2lat

en_wiki = pywikibot.Site("en", "wikipedia")
sr_wiki = pywikibot.Site("sr", "wikipedia")
wikidata = pywikibot.Site("wikidata", "wikidata")
wiki_repo = wikidata.data_repository()

logger = tools.get_logger(__name__)


class AbstractCheck(object):
    applicable_on = []
    maps_applicable_on = ['*']
    depends_on = []
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

    @staticmethod
    def entity_type(entity):
        """
        Helper method to get type of the entity.
        :param entity: Entity to get type from
        :return: Type of the entity. Can be one of the 'node', 'way', 'relation'
        """
        try:
            import osmread
            if isinstance(entity, osmread.Node):
                return 'node'
            elif isinstance(entity, osmread.Way):
                return 'way'
            elif isinstance(entity, osmread.Relation):
                return 'relation'
        except ImportError:
            pass
        try:
            import osmium
            if isinstance(entity, osmium.osm.Node):
                return 'node'
            elif isinstance(entity, osmium.osm.Way):
                return 'way'
            elif isinstance(entity, osmium.osm.Relation):
                return 'relation'
        except ImportError:
            pass
        raise Exception('Entity is neither PyOsmium not osmread known type'.format(entity))

    @staticmethod
    def ask_confirmation(input_text, entity):
        """
        Simple wrapper to ask user to do something. Method will append "(y/n)" and dump entity
        :param input_text: Text to ask. 
        :param entity: entity for whcih question is being asked
        :return: True if user confirmed, False otherwise
        """
        for tag_name, tag_value in entity.tags.items():
            print('{0}: {1}'.format(tag_name, tag_value))
        print('https://www.openstreetmap.org/{0}/{1}'.format(AbstractCheck.entity_type(entity), entity.id))
        response = input('{0} (Y/n)?'.format(input_text))
        if response == '' or response.lower() == 'y':
            return True
        return False


class NameMissingCheck(AbstractCheck):
    """
    Checks that 'name' tag is present in entity.
    """
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['Serbia']

    def __init__(self, entity_context):
        super(NameMissingCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'name' not in entity.tags:
            place_type = entity.tags['place']
            return 'Name missing for {0} with id {1}: {2}'.format(place_type, entity.id, entity)
        return ''


class NameCyrillicCheck(AbstractCheck):
    """
    Checks that name of the entity is in cyrillic script.
    """
    depends_on = [NameMissingCheck]
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['Serbia']

    def __init__(self, entity_context):
        super(NameCyrillicCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'name' in entity.tags and not at_least_some_in_cyrillic(entity.tags['name']):
            place_type = entity.tags['place']
            return 'Seems that {0} name is not in cyrillic for "{1}"'.format(place_type, entity.tags['name'])
        return ''


class LatinNameExistsCheck(AbstractCheck):
    """
    Checks that for entity exists name in sr-Latn too.
    """
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['*']
    is_fixable = True

    def __init__(self, entity_context):
        super(LatinNameExistsCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if (self.map == 'Serbia' and 'name:sr-Latn' not in entity.tags) or\
                (self.map != 'Serbia' and 'name:sr' in entity.tags):
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Latin name missing for {0} {1}'.format(place_type, name)
        return ''

    def fix(self, entity, api):
        if NameMissingCheck(self.entity_context).do_check(entity) != '':
            # We cannot automatically set latin name, if cyrillic is not set
            return ''
        if NameCyrillicCheck(self.entity_context).do_check(entity) != '':
            # Doesn't make sense to set latin name, if original name is not in cyrillic
            return ''

        name = entity.tags['name'] if self.map == 'Serbia' else entity.tags['name:sr']
        latin_name = cyr2lat(name)
        question = 'Are you sure you want to append tag "name:sr-Latn" with value "{0}" to entity "{1}"'.format(
            latin_name, name
        )

        if self.entity_type(entity) == 'way':
            way = api.WayGet(entity.id)
            if 'name:sr-Latn' not in way['tag']:
                if self.ask_confirmation(question, entity):
                    way['tag']['name:sr-Latn'] = latin_name
                    if not self.dry_run:
                        api.WayUpdate(way)
                    return 'name:sr-Latn for way {0} didn\'t exists, added it as "{1}"'.format(name, latin_name)
        elif self.entity_type(entity) == 'node':
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
    depends_on = [NameMissingCheck, NameCyrillicCheck, LatinNameExistsCheck]
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['*']
    is_fixable = True

    def __init__(self, entity_context):
        super(LatinNameSameAsCyrillicCheck, self).__init__(entity_context)

    def do_check(self, entity):
        latin_name = entity.tags['name:sr-Latn']
        cyrillic_name = entity.tags['name'] if self.map == 'Serbia' else entity.tags['name:sr']
        if cyr2lat(cyrillic_name) != latin_name:
            place_type = entity.tags['place']
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
        if self.entity_type(entity) == 'way':
            way = api.WayGet(entity.id)
            online_name = way['tag']['name'] if self.map == 'Serbia' else way['tag']['name:sr']
            if 'name:sr-Latn' in way['tag'] and online_name == name and way['tag']['name:sr-Latn'] == old_latin_name:
                if self.ask_confirmation(question, entity):
                    way['tag']['name:sr-Latn'] = correct_latin_name
                    if not self.dry_run:
                        api.WayUpdate(way)
                    return 'name:sr-Latn for way {0} was different than in cyrillic, fixed it to be "{1}"'.format(
                        name, correct_latin_name)
        elif self.entity_type(entity) == 'node':
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
    Check that sr-Latn name in tags in not in cyrillic script.
    """
    depends_on = [NameMissingCheck, LatinNameExistsCheck]
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['*']

    def __init__(self, entity_context):
        super(LatinNameNotInCyrillicCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'name:sr-Latn' in entity.tags and at_least_some_in_cyrillic(entity.tags['name:sr-Latn']):
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'There is cyrillic in {0} name {1} for latin version {2}'.format(
                place_type, name, entity.tags['name:sr-Latn'])
        return ''


class WikipediaEntryExistsCheck(AbstractCheck):
    """
    Check that there exists Wikipedia entry for entity.
    """
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['Serbia']

    def __init__(self, entity_context):
        super(WikipediaEntryExistsCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'wikipedia' not in entity.tags:
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Wikipedia missing for {0} {1}'.format(place_type, name)
        return ''


class WikipediaEntryIsInSerbianCheck(AbstractCheck):
    """
    Check that Wikipedia entry for entity is in local Wikipedia, e.g. Serbian.
    """
    depends_on = [WikipediaEntryExistsCheck]
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['Serbia']

    def __init__(self, entity_context):
        super(WikipediaEntryIsInSerbianCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if not entity.tags['wikipedia'].startswith('sr:'):
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Wikipedia entry is {0} and is not in Serbian for {1} {2}'.format(
                entity.tags['wikipedia'], place_type, name)
        return ''


class WikipediaEntryValidCheck(AbstractCheck):
    """
    Checks that Wikipedia entry for a given entity actually exists in Wikipedia.
    """
    depends_on = [WikipediaEntryExistsCheck, WikipediaEntryIsInSerbianCheck]
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['Serbia']

    def __init__(self, entity_context):
        super(WikipediaEntryValidCheck, self).__init__(entity_context)

    def do_check(self, entity):
        page = pywikibot.Page(sr_wiki, entity.tags['wikipedia'][3:])
        try:
            pywikibot.ItemPage.fromPage(page)
            return ''
        except pywikibot.exceptions.NoPage:
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Wikipedia entry {0} does not exist for {1} {2}'.format(
                entity.tags['wikipedia'][3:], place_type, name)


class WikidataEntryExistsCheck(AbstractCheck):
    """
    Check that there exists Wikidata entry for entity. 
    """
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['Serbia']

    def __init__(self, entity_context):
        super(WikidataEntryExistsCheck, self).__init__(entity_context)

    def do_check(self, entity):
        if 'wikidata' not in entity.tags:
            place_type = entity.tags['place']
            name = entity.tags['name'] if 'name' in entity.tags else entity.id
            return 'Wikidata missing for {0} {1}'.format(place_type, name)
        return ''


class WikidataEntryValidCheck(AbstractCheck):
    """
    Checks that Wikidata entry for a given entity actually exists in Wikidata.
    """
    depends_on = [WikidataEntryExistsCheck]
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['Serbia']

    def __init__(self, entity_context):
        super(WikidataEntryValidCheck, self).__init__(entity_context)

    def do_check(self, entity):
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
    depends_on = [WikipediaEntryValidCheck, WikidataEntryValidCheck]
    applicable_on = [City, Town, Village]
    maps_applicable_on = ['Serbia']

    def __init__(self, entity_context):
        super(WikipediaAndWikidataInSyncCheck, self).__init__(entity_context)

    def do_check(self, entity):
        wikidata_entry = self.entity_context['local_store']['wikidata']
        if wikidata_entry.text['labels']['sr'] != entity.tags['wikipedia'][3:]:
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
    maps_applicable_on = ['Serbia']
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
        if self.entity_type(entity) == 'way':
            way = api.WayGet(entity.id)
            if 'is_in:country' not in way['tag']:
                way['tag']['is_in:country'] = 'Serbia'
                if not self.dry_run:
                    api.WayUpdate(way)
                return 'is_in:country for way {0} was missing, added it to be "{1}"'.format(name, 'Serbia')
        if self.entity_type(entity) == 'node':
            node = api.NodeGet(entity.id)
            if 'is_in:country' not in node['tag']:
                node['tag']['is_in:country'] = 'Serbia'
                if not self.dry_run:
                    api.NodeUpdate(node)
                return 'is_in:country for node {0} was missing, added it to be "{1}"'.format(name, 'Serbia')
        return ''

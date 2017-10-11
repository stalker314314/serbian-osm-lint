# -*- coding: utf-8 -*-


class Applicability(object):
    """
    Interface that all methods testing applicability should satisfy. 
    """
    @staticmethod
    def is_entity_applicable(entity):
        """
        :param entity: Entity for which to check applicability 
        :return: True if applicable, False otherwise
        """
        return False


class City(Applicability):
    """
    Check that entity is city.
    """
    @staticmethod
    def is_entity_applicable(entity):
        return 'place' in entity.tags and entity.tags['place'] == 'city'


class Town(Applicability):
    """
    Check that entity is city.
    """
    @staticmethod
    def is_entity_applicable(entity):
        return 'place' in entity.tags and entity.tags['place'] == 'town'

class Village(Applicability):
    """
    Check that entity is village.
    """
    @staticmethod
    def is_entity_applicable(entity):
        return 'place' in entity.tags and entity.tags['place'] == 'village'
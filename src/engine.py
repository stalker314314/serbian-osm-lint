# -*- coding: utf-8 -*-

from enum import Enum

import tools

logger = tools.get_logger(__name__)


class Result(Enum):
    NOT_APPLICABLE = 1
    DEPENDENCY_NOT_SATISFIED = 2
    CHECKED_OK = 3
    CHECKED_ERROR = 4


class CheckEngine(object):
    """
    Main engine that do check dependency resolution, applicability resolution and perform all checks on one entity.
    """
    def __init__(self, check_classes, entity, global_context):
        self.check_classes = check_classes[:]
        self.entity = entity
        self.global_context = global_context

    @staticmethod
    def do_entity_check_and_fix(check, entity):
        """
        Takes one entity and one check and performs check.
        If check is erroneous, it will also try to fix error (if it is possible and allowed).
        :param check: Check to perform
        :param entity: Entity to check
        :return: String that tells what check did. If it is empty, it means there is no problem.
        """
        name = entity.tags['name'] if 'name' in entity.tags else entity.id
        message = check.do_check(entity)
        if message != '': # OK, check is erroneous, let's see if we can perform fix
            if check.entity_context['global_context']['fix']:
                message_fixed = check.fix(entity, check.entity_context['global_context']['api'])
                if message_fixed != '':
                    logger.debug('[%s] %s', check.entity_context['global_context']['map'], message_fixed)
        return message

    def check_all(self, filter_not_checked=True):
        """
        Main method that does all checks.
        :param filter_not_checked: If True, engine will remove all checks that resulted in not applicable
        or dependecy not satisfied errors. This significantly lower memory footprint and is not needed for report.
        :return: Dictionary of all check with name of the check class as key
        """
        entity_context = {'checks': {}, 'local_store': {}, 'global_context': self.global_context}

        while True:
            processed_any_cls = None
            for check_cls in self.check_classes:
                check_cls_name = check_cls.__name__

                # Test if we do check this on this entity
                if not any(a for a in check_cls.applicable_on if a.is_entity_applicable(self.entity)):
                    entity_context['checks'][check_cls_name] = {
                        'result': Result.NOT_APPLICABLE,
                        'messages': [],
                        'fixable': False}
                    processed_any_cls = check_cls
                    break

                # Test if this map is applicable on this check
                map_applicable = False
                map_name = self.global_context['map']
                for map_possible in check_cls.maps_applicable_on:
                    if map_possible == '*':
                        map_applicable = True
                        break
                    elif map_possible.startswith('!') and map_possible != map_name:
                        map_applicable = True
                        break
                    elif map_possible == map_name:
                        map_applicable = True
                        break
                if not map_applicable:
                    entity_context['checks'][check_cls_name] = {
                        'result': Result.DEPENDENCY_NOT_SATISFIED,
                        'messages': [],
                        'fixable': False}
                    processed_any_cls = check_cls
                    break

                # Test if all dependency are satisfied
                satisfied = True
                for dc_cls in check_cls.depends_on:
                    dc_cls_name = dc_cls.__name__
                    if dc_cls_name in entity_context['checks']:
                        result = entity_context['checks'][dc_cls_name]['result']
                        if result != Result.CHECKED_OK:
                            logger.debug('[%s] Dependency %s was %s and check %s not satisfied',
                                         map_name, dc_cls_name, result, check_cls_name)
                            entity_context['checks'][check_cls_name] = {'result': Result.DEPENDENCY_NOT_SATISFIED,
                                                                        'messages': [],
                                                                        'fixable': False}
                            processed_any_cls = check_cls
                            satisfied = False
                            break
                    else:
                        logger.debug('[%s] Dependency %s still not checked, skipping check %s for now',
                                     map_name, dc_cls_name, check_cls_name)
                        satisfied = False
                        break
                if satisfied:
                    logger.debug('[%s] Check %s applicable and all dependencies satisfied, doing check',
                                 map_name, check_cls_name)
                    message = CheckEngine.do_entity_check_and_fix(check_cls(entity_context), self.entity)
                    if message == '':
                        entity_context['checks'][check_cls_name] = {'result': Result.CHECKED_OK,
                                                                    'messages': [],
                                                                    'fixable': False}
                    else:
                        entity_context['checks'][check_cls_name] = {'result': Result.CHECKED_ERROR,
                                                                    'messages': [message],
                                                                    'fixable': check_cls.is_fixable}
                    processed_any_cls = check_cls
                    break

            if not processed_any_cls:
                if len(self.check_classes) == 0:
                    break
                raise Exception('Circular dependency in configuration')
            else:
                self.check_classes.remove(processed_any_cls)

        # We don't care in reporting for unsatisfiable dependencies nor for not applicable checks, so filter those out
        filtered_checks = {}
        for check_cls_name in entity_context['checks']:
            check = entity_context['checks'][check_cls_name]
            if (not filter_not_checked) or\
                    check['result'] == Result.CHECKED_OK or check['result'] == Result.CHECKED_ERROR:
                filtered_checks[check_cls_name] = check
        return filtered_checks

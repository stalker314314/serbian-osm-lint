# -*- coding: utf-8 -*-

from enum import Enum
from osmapi.OsmApi import ElementDeletedApiError

import tools

logger = tools.get_logger(__name__)


class Result(Enum):
    NOT_APPLICABLE = 1
    CHECKED_OK = 2
    CHECKED_ERROR = 3


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
                message_fixed = ''
                try:
                    message_fixed = check.fix(entity, check.entity_context['global_context']['api'])
                except ElementDeletedApiError as e:
                    # This can happen during fixing, just ignore and continue
                    logger.exception(e)
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

        for check_cls in self.check_classes:
            check_cls_name = '{0}.{1}'.format(check_cls.__module__, check_cls.__name__)

            # Test if we do check this on this entity
            if not any(a for a in check_cls.applicable_on if a.is_entity_applicable(self.entity)):
                entity_context['checks'][check_cls_name] = {
                    'result': Result.NOT_APPLICABLE,
                    'messages': [],
                    'fixable': False}
                continue

            message = CheckEngine.do_entity_check_and_fix(check_cls(entity_context), self.entity)
            if message == '':
                entity_context['checks'][check_cls_name] = {'result': Result.CHECKED_OK,
                                                            'messages': [],
                                                            'fixable': False}
            else:
                entity_context['checks'][check_cls_name] = {'result': Result.CHECKED_ERROR,
                                                            'messages': [message],
                                                            'fixable': check_cls.is_fixable}

        # We don't care in reporting for unsatisfiable dependencies nor for not applicable checks, so filter those out
        filtered_checks = {}
        for check_cls_name in entity_context['checks']:
            check = entity_context['checks'][check_cls_name]
            if (not filter_not_checked) or\
                    check['result'] == Result.CHECKED_OK or check['result'] == Result.CHECKED_ERROR:
                filtered_checks[check_cls_name] = check
        return filtered_checks

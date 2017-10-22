# -*- coding: utf-8 -*-

import logging.handlers


def setup_logger(logging_level=logging.INFO):
    """
    Simple logger used throughout whole code - logs both to file and console
    """
    logger = logging.getLogger('serbian-osm-lint')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    ch = logging.handlers.TimedRotatingFileHandler(filename='serbian-osm-lint.log', when='midnight', interval=1,
                                                   encoding='utf-8')
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    ch = logging.StreamHandler()
    ch.setLevel(logging_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


def get_logger(name):
    return logging.getLogger('serbian-osm-lint.{0}'.format(name))

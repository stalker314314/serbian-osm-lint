# -*- coding: utf-8 -*-


class CalculateDistanceException(Exception):
    def __init__(self, message):
        super(CalculateDistanceException, self).__init__()
        self.message = message

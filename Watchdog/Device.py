#!/usr/bin/env python

"""
    generic device class

"""

import logging
import time

class Device:

    def __init__(self, address, name):

        self._address = address
        self._name = name
        self._timestamp = 0
        self._online = False

    def check(self, callback):
        """
        set online flag: overwritten by derived class
        """
        pass

    def update(self):
        self._timestamp = time.time()
        logging.debug("Timestamp: %d" % self._timestamp)

    @property
    def address(self): return self._address

    @property
    def name(self): return self._name

    @property
    def online(self): return self._online

    @online.setter
    def online(self, value): self._online = value


if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', level=logging.DEBUG)

    dev = Device("127.0.0.1", "localhost")
    logging.debug("Device object [%s] created!", dev._name)

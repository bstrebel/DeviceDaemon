#!/usr/bin/env python

"""
    generic device class

"""

import logging
import time

class Device:

    def __init__(self, logger, address, name):

        self._logger = logger
        self._address = address
        self._name = name
        self._timestamp = 0
        self._online = None
        self._zone = None
        self._update = None

    def check(self, callback):
        """
        set online flag: overwritten by derived class
        """
        pass

    def update(self):
        self._timestamp = time.time()
        # self._logger.debug("Timestamp: %d" % self._timestamp)

# region Properties
    @property
    def age(self): return time.time() - self._timestamp

    @property
    def address(self): return self._address

    @property
    def name(self): return self._name

    @property
    def online(self): return self._online

    @online.setter
    def online(self, value): self._online = value

    # @property
    # def update(self): return self._update
    #
    # @update.setter
    # def update(self, value): self._update = value

    @property
    def zone(self): return self._zone

    @zone.setter
    def zone(self, value): self._zone = value
# endregion

if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', level=logging.DEBUG)

    dev = Device("127.0.0.1", "localhost")
    logging.debug("Device object [%s] created!", dev._name)

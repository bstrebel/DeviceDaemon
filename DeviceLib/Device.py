#!/usr/bin/env python

"""
    generic device class

"""

import logging
import time

class Device:

    def __init__(self, logger, config):

        assert isinstance(logger, logging.Logger)
        self._logger = logger
        self._key = config['key']

        #self._address = address
        #self._name = name
        self._timestamp = 0
        self._online = None
        self._zone = None
        self._update = None

        self._config = config

    def callback(self, key):
        if 'callback' in self._config and key in self._config['callback']:
            if callable(self._config['callback'][key]):
                try:
                    self._config['callback'][key](self)
                except:
                    self._logger.exception("Callback [%s] throwed exception!" % (self._config['callback'][key].__name__))
            else:
                self._logger.error("Invalid callback specification [%s]" % (self._config['callback'][key]))
        else:
            self._logger.warn("No callback defined for event [%s]" % (key))

    def check(self, callback):
        """
        set online flag: overwritten by derived class
        """
        pass

    def update(self):
        self._timestamp = time.time()
        # self._logger.debug("Timestamp: %d" % self._timestamp)

    def config(self,key):
        if key in self._config:
            return self._config[key]
        return None

# region Properties
    @property
    def key(self): return self._key

    @property
    def age(self): return time.time() - self._timestamp

    # @property
    # def address(self): return self._address

    # @property
    # def name(self): return self._name

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

    dev = Device(logging.getLogger(), {'key': 'device',  })
    logging.debug("Device object [%s] created!", dev._key)

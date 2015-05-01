#!/usr/bin/env python

"""
    Watchdog Controller
    check devices by bluetooth address or hostname

"""
__version__ = "0.1"
__author__ = 'bst'

import bluetooth
import select
import re
import ConfigParser
import time
import os

#from BluetoothDevice import *
#from PingDevice import *

class WatchdogController():

    def __init__(self, home=".", logger=None):

        self._home = home
        self._logger = logger

        # logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s',
        #                    filename=home + "/controller.log",
        #                    level=logging.DEBUG)

        self._logger.debug("Controller constructor ...")

    def init(self):
        self._logger.warning("Controller init ...")

    def exit(self):
        self._logger.warning("Controller exit ...")

    def run(self):

        while True:
            self._logger.debug("Controller main loop ...")
            time.sleep(10)

    def reload(self):
        self._logger.warning("Controller reload ...")

    @property
    def home(self): return self._home


def main():

    import logging

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', level=logging.DEBUG)
    logger = logging.getLogger()

    home = os.path.expanduser("~") + "/.DeviceDaemon"

    controller = WatchdogController(home, logger)
    controller.run()


if __name__ == '__main__':
    main()



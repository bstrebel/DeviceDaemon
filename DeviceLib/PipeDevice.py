#!/usr/bin/env python

"""
    check devices by ip address or hostname

"""
__version__ = "1.0"
__author__ = 'bst'

import os
import select
import subprocess
import re
import socket

from Device import *


class PipeDevice(Device):

    _devnull = open(os.devnull, 'w')

    def __init__(self, logger, identifier):

        self._logger = logger
        Device.__init__(self, logger=self._logger, address=identifier, name=identifier)

    def check(self, callback):
        return True


class PipeDiscoverDevice:

    def __init__(self, options):

        self._logger = options['logger']
        self._callback = options['callback']
        self._fifo_name = options['path']
        self._fifo = None


    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    def listen(self):

        if self._fifo is not None:
            self.close()

        if not os.path.exists(self._fifo_name):
            os.mkfifo(self._fifo_name)

        self._fifo = os.open(self._fifo_name, os.O_RDONLY|os.O_NONBLOCK)

    def close(self):

        if self._fifo is not None:
            os.close(self._fifo)
            self._fifo = None

        if os.path.exists(self._fifo_name):
            os.unlink(self._fifo_name)

    def process_event(self):

        self._buffer = ''
        self._buffer = os.read(self._fifo, 4096)

        if not self._buffer:
            # select() returns True until close and re-open of the pipe !?
            os.close(self._fifo)
            self._fifo = os.open(self._fifo_name, os.O_RDONLY|os.O_NONBLOCK)
        else:
            self._buffer = self._buffer.rstrip()
            # TODO: process buffer

        return self._buffer

    def discover(self):
        for addr, device in self._devices.items():
            device.check(self._callback)

    def expired(self, seconds):

        for addr, device in self._devices.items():
            if device.age > seconds:
                self._logger.debug("Expired: %s" % device.name)
                del device
                del self._devices[addr]

    @property
    def fifo(self): return self._fifo

    @property
    def fifo_name(self): return self._fifo_name


# region __Main__
if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', level=logging.DEBUG)

    def evt_new():
        pass

    def evt_off():
        pass

    def evt_req():
        pass

    options = { 'logger': logging.getLogger(),
                'path': '/tmp/DeviceDaemon.fifo',
                'callback': {'new': evt_new, 'off': evt_off, 'req': evt_req()}}

    with PipeDiscoverDevice(options) as discover:

        discover.listen()

        rf = [discover.fifo, ]

        while True:

            try:
                rfds = select.select(rf, [], [])[0]

                if discover.fifo in rfds:
                    buffer = discover.process_event()
                    if buffer: print buffer

            except KeyboardInterrupt:

                discover.close()
                exit(0)

            # time.sleep(1)

# endregion

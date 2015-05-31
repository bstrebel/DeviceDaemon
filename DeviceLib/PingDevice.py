#!/usr/bin/env python

"""
    check devices by ip address or hostname

"""
__version__ = "1.0"
__author__ = 'bst'

import os
import subprocess
import re
import socket

from Device import *
from ping import do_one


class PingDevice(Device):

    _pattern = re.compile("\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}")
    _devnull = open(os.devnull, 'w')

    @staticmethod
    def _ping(host):
        if os.geteuid() == 0:
            # running as root => use python ICMP            '''
            try:
                return do_one(host, 1, 64)
            except socket.error:
                return None
        else:
            # running suid ping as non-root user
            if subprocess.call(["ping", "-q", "-c1", "-W1", host], stdout=PingDevice._devnull,
                               stderr=PingDevice._devnull) == 0:
                return True
            else:
                return None

    def __init__(self, logger, identifier):

        self._logger = logger

        if self._pattern.match(identifier):
            address = identifier
            try:
                name = socket.gethostbyaddr(address)[0]
            except socket.error:
                name = None
        else:
            name = identifier
            try:
                address = socket.gethostbyname(name)
            except socket.error:
                address = None

        Device.__init__(self, logger=self._logger, address=address, name=name)

    def check(self, callback):
        """
        Check IP device status with ICMP ping
        :param callback: dictionary of callback functions
        :return: True, if device is online
        """
        host = None
        if self._address is None:
            host = self._name
            try: address = socket.gethostbyname(self._name)
            except: pass
        else:
            host = self._address

        if host is None:
            return False

        result = self._ping(host)
        self.update()
        self._logger.debug('Ping device [%s] %s: %s' % (self._address, self._name, "Offline" if result is None else "Online"))

        if result is None:
            if self._online:
                # self._logger.debug("Off: %s", self._address)
                callback['off'](self)
                self._online = False

            return False
        else:
            if not self._online:
                # self._logger.debug("New: %s", self._address)
                callback['new'](self)
                self._online = True

            return True


class PingDiscoverDevice():

    def __init__(self, options):

        self._logger = options['logger']
        self._callback = options['callback']

        self._devices = {}
        for device in options['devices']:
            d = PingDevice(self._logger, device)
            self._devices[d.address] = d

    def discover(self):
        for addr, device in self._devices.items():
            device.check(self._callback)

    def expired(self, seconds):

        for addr, device in self._devices.items():
            if device.age > seconds:
                self._logger.debug("Expired: %s" % device.name)
                del device
                del self._devices[addr]


if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', level=logging.DEBUG)

    # dev = PingDevice(sys.argv[1])
    # dev.check()
    # print(dev._address)
    # print(dev._name)
    # print(dev._online)

    def evt_new(ping_device):
        print("Found new device [%s]" % ping_device.address)

    def evt_off(ping_device):
        print("Device [%s] disappeared" % ping_device.address)


    callback = {'new': evt_new, 'off': evt_off}
    devices = ['127.0.0.1', 'sensor', 'htc', 'access']

    options = { 'logger': logging.getLogger(),
                'callback': {'new': evt_new, 'off': evt_off},
                'devices': ['127.0.0.1', '172.16.0.1', '172.16.255.42']}

    discover = PingDiscoverDevice(options)

    while True:
        discover.discover()
        time.sleep(10)

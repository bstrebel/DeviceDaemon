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
import threading
import requests
import random

from Device import *
from ping import send_one_ping, receive_one_ping, do_one

class PingDevice(Device):

    _pattern = re.compile("\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}")
    _devnull = open(os.devnull, 'w')

    def _ping(self):

        if os.geteuid() == 0:
            # running as root => use python ICMP            '''
            try:
                send_one_ping(self._socket, self._address, self._socket_id, self._psize)
                delay = receive_one_ping(self._socket, self._socket_id, self._timeout)
                if delay is not None:
                    return True
                else:
                    return False
            except socket.error as e:
                return None
        else:
            # running suid ping as non-root user
            if subprocess.call(["ping", "-q", "-c1", "-W1", self._address], stdout=PingDevice._devnull,
                               stderr=PingDevice._devnull) == 0:
                return True
            else:
                return None

    def done(self):
        try:
            self._socket.close()
        except: pass

    def __init__(self, logger, identifier, status, number):

        self._logger = logger
        self._status = status
        self._socket = None
        self._icmp = None
        self._psize = 64
        self._timeout = 1
        self._socket_id = ( os.getpid() + number) & 0xFFFF

# region socket initialization
        self._icmp = socket.getprotobyname("icmp")
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, self._icmp)
        except socket.error, (errno, msg):
            if errno == 1:
                # Operation not permitted
                msg += " - Note that ICMP messages can only be sent from processes"
                raise socket.error(msg)
            raise # raise the original error
# endregion

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

        result = self._ping()

        if result is not None:

            self.update()

            self._logger.debug('Ping device [%s] %s: %s' % (self._address, self._name, "Online" if result else "Offline"))

            if result is False:
                # device offline
                if (self._online is True) or (self._online is None and self._status is True):
                    callback['off'](self)
                self._online = False
            else:
                # device online
                if (self._online is False) or (self._online is None and self._status is False):
                    callback['new'](self)
                self._online = True

        return self._online


class PingDiscoverDevice(threading.Thread):

    def __init__(self, options, device):

        threading.Thread.__init__(self)
        self._tag = device
        self._number = int(self.name.split('-',2)[1])
        self._logger = options['logger']
        self._callback = options['callback']
        self._sleep = options['sleep']
        self._device = PingDevice(self._logger, device, options['online'], self._number)

    def run(self):
        self._logger.info("Ping %s for [%s] started ..." % (self.name, self._tag))
        while not shutdown:
            try:
                self._device.check(self._callback)
                time.sleep(self._sleep)
            except: pass
        self._device.done()
        self._logger.info("Ping %s for [%s] stopped!" % (self.name, self._tag))


# region __main__
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


    # callback = {'new': evt_new, 'off': evt_off}
    # devices = ['127.0.0.1', 'sensor', 'htc', 'access']

    options = { 'logger': logging.getLogger(),
                'sleep': 10,
                'online': True,
                'callback': {'new': evt_new, 'off': evt_off},
                'devices': ['localhost','access','opti960','easybox'],
                'localhost': {'address': '127.0.0.1', 'sleep': 10, 'online': True},
                'access': {'sleep': 3, 'online': False}}

    shutdown = False
    threads = []

    for device in options['devices']:
        if device not in options:
            options[device] = {}
        for key in [ 'logger', 'sleep', 'callback', 'online']:
            if key in options:
                if key not in options[device]:
                    options[device][key] = options[key]

        thread = PingDiscoverDevice(options[device], device)
        thread.start()
        threads.append(thread)

    # for thread in threads:
    #     thread.join()

    while True:
        try:
            print "Main Loop ..."
            time.sleep(10)
        except KeyboardInterrupt:
            shutdown = True
            # for thread in threads:
            #    thread.join()
            exit(0)

# endregion

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
import copy

from Device import *
from ping import send_one_ping, receive_one_ping, do_one

class PingDevice(Device, threading.Thread):

    _pattern = re.compile("\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}")
    _devnull = open(os.devnull, 'w')

    def __init__(self, logger, device):

        threading.Thread.__init__(self)
        self._number = int(self.name.split('-',2)[1])
        self._logger = logger
        self._socket_id = ( os.getpid() + self._number) & 0xFFFF
        self._socket = None
        self._icmp = None
        self._callback = None if 'callback' not in device else device['callback']
        self._sleep = 1 if 'sleep' not in device else device['sleep']
        self._psize = 64 if 'psize' not in device else device['psize']
        self._timeout = 1 if 'timeout' not in device else device['timeout']
        self._retry = 1 if 'retry' not in device else device['retry']
        self._shutdown = False

# region check device ip/dns
        if 'dns' in device and 'ip' not in device:
            try:
                device['ip'] = socket.gethostbyname(device['dns'])
            except socket.error:
                device['ip'] = None
        elif 'ip' in device and 'dns' not in device:
            try:
                device['dns'] = socket.gethostbyaddr(device['ip'])[0]
            except socket.error:
                device['dns'] = None
        elif 'ip' not in device and 'dns' not in device:
            # self._logger.error('Invalid specification for ping device [%s]' % (device['key']))
            raise ValueError('IP address or DNS name is required for a ping device')

        if device['ip'] is None:
            # self._logger.error('Cannot determin IP address for device [%s]' % device['dns'])
            raise ValueError('Cannot determin IP address for device [%s]' % device['dns'])

# endregion

        # self._address = device['ip']
        # self._name = device['dns']
        self._status = True if 'online' not in device else device['online']

        Device.__init__(self, self._logger, device)

# region socket initialization
        if os.geteuid() == 0:
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

    def run(self):
        self._logger.info("Ping %s for [%s] started ..." % (self.name, self._key))
        while not self._shutdown:
            self.check(self._callback)
            try:
                time.sleep(self._sleep)
            except:
                break
        self.done()
        self._logger.info("Ping %s for [%s] stopped!" % (self.name, self._key))

    def shutdown(self):
        self._shutdown = True

    def done(self):
        if self._socket is not None:
            try:
                self._socket.close()
            except: pass

    def _ping(self):

        if os.geteuid() == 0:
            # running as root => use python ICMP            '''
            try:
                send_one_ping(self._socket, self.ip, self._socket_id, self._psize)
                delay = receive_one_ping(self._socket, self._socket_id, self._timeout)
                if delay is not None:
                    return True
                else:
                    return False
            except socket.error as e:
                return None
        else:
            # running suid ping as non-root user
            timeout = "-W" + str(self._timeout)
            retry = "-c" + str(self._retry)
            if subprocess.call(["ping", "-q", retry, timeout, self.ip], stdout=PingDevice._devnull,
                               stderr=PingDevice._devnull) == 0:
                return True
            else:
                return False

    def check(self, callback):
        """
        Check IP device status with ICMP ping
        :param callback: dictionary of callback functions
        :return: True, if device is online
        """
        if self.ip is None:
            self._logger.error("Missing ip address for device [%s]" % self.dns)
            return None

        result = self._ping()

        if result is not None:

            self.update()

            self._logger.debug('Ping device [%s] %s: %s' % (self.ip, self.dns, "Online" if result else "Offline"))

            if result is False:
                # device offline
                if (self._online is True) or (self._online is None and self._status is True):
                        Device.callback(self, 'off')
                self._online = False
            else:
                # device online
                if (self._online is False) or (self._online is None and self._status is False):
                    Device.callback(self, 'new')
                self._online = True

        return self._online

    @property
    def ip(self): return self._config['ip']

    @property
    def dns(self): return self._config['dns']


class PingDiscoverDevice():

    def __init__(self, logger, options, devices):

        self._logger = logger
        self._options = options
        self._devices = {}
        self._threads = []

        for device in options['devices']:

            if device in devices:
                self._devices[device] = copy.deepcopy(devices[device])
            else:
                self._devices[device] = {}
                self._devices[device]['key'] = device
                self._devices[device]['dns'] = device

            for key in ['psize', 'timeout', 'sleep', 'callback', 'online']:
                if key in self._options:
                    if key not in self._devices[device]:
                        self._devices[device][key] = self._options[key]

    def listen(self):

        for device in self._devices:

            try:
                thread = PingDevice(self._logger, self._devices[device])
                thread.start()
                self._threads.append(thread)
            except ValueError, e:
                self._logger.error(e.message)


    def shutdown(self):
        for thread in self._threads:
            thread.shutdown()

# region __main__
if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', level=logging.DEBUG)

    def evt_new(ping_device):
        assert isinstance(ping_device, PingDevice)
        print("Found new device [%s]" % ping_device.ip)

    def evt_off(ping_device):
        assert isinstance(ping_device, PingDevice)
        print("Device [%s] disappeared" % ping_device.ip)


    # callback = {'new': evt_new, 'off': evt_off}
    # devices = ['127.0.0.1', 'sensor', 'htc', 'access']

    logger = logging.getLogger()

    options = {'sleep': 10,
               'timeout': 1,
               'psize': 64,
               'online': True,
               'callback': {'new': evt_new, 'off': evt_off},
               'devices': ['easybox', 'access', 'opti960']}

    devices = {'access': {'key': 'access', 'dns': 'access', 'sleep': 1, 'online': False},
               'opti960': {'key': 'opti960', 'dns': 'opti960', 'sleep': 1, 'online': False},
               'easybox': {'key': 'easybox', 'dns': 'easybox', 'sleep': 10, 'online': True}
               }

    discover = PingDiscoverDevice(logger, options, devices)
    discover.listen()

    while True:
        print "Main Loop ..."
        try:
            time.sleep(60)
        except KeyboardInterrupt:
            discover.shutdown()
            exit(0)

# endregion

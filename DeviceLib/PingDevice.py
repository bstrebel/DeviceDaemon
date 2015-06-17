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
                send_one_ping(self._socket, self.address, self._socket_id, self._psize)
                delay = receive_one_ping(self._socket, self._socket_id, self._timeout)
                if delay is not None:
                    return True
                else:
                    return False
            except socket.error as e:
                return None
        else:
            # running suid ping as non-root user
            if subprocess.call(["ping", "-q", "-c1", "-W1", self.address], stdout=PingDevice._devnull,
                               stderr=PingDevice._devnull) == 0:
                return True
            else:
                return None

    def done(self):
        try:
            self._socket.close()
        except: pass

    def __init__(self, logger, number, device):

        self._logger = logger
        self._socket_id = ( os.getpid() + number) & 0xFFFF
        self._socket = None
        self._icmp = None
        self._psize = 64 if 'psize' not in device else device['psize']
        self._timeout = 1 if 'timeout' not in device else device['timeout']

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
            self._logger.error('Invalid specification for ping device [%s]' % (device['key']))
            raise ValueError('IP address or DNS name is required for a ping device')
# endregion

        # self._address = device['ip']
        # self._name = device['dns']
        self._status = True if 'online' not in device else device['online']

        Device.__init__(self, self._logger, device)

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

    def check(self):
        """
        Check IP device status with ICMP ping
        :param callback: dictionary of callback functions
        :return: True, if device is online
        """
        result = self._ping()

        if result is not None:

            self.update()

            self._logger.debug('Ping device [%s] %s: %s' % (self.address, self.name, "Online" if result else "Offline"))

            if result is False:
                # device offline
                if (self._online is True) or (self._online is None and self._status is True):
                        Device.callback(self,'off')
                self._online = False
            else:
                # device online
                if (self._online is False) or (self._online is None and self._status is False):
                    Device.callback(self,'new')
                self._online = True

        return self._online

    @property
    def address(self): return self._config['ip']

    @property
    def name(self): return self._config['dns']


class PingDiscoverDevice(threading.Thread):

    def __init__(self, logger, device):

        threading.Thread.__init__(self)
        self._logger = logger

        self._key = device['key']
        self._number = int(self.name.split('-',2)[1])
        #self._callback = device['callback']
        self._sleep = device['sleep']
        self._device = PingDevice(self._logger, self._number, device)

    def run(self):
        self._logger.info("Ping %s for [%s] started ..." % (self.name, self._key))
        while not shutdown:
            self._device.check()
            try:
                time.sleep(self._sleep)
            except:
                break
        self._device.done()
        self._logger.info("Ping %s for [%s] stopped!" % (self.name, self._key))


# region __main__
if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', level=logging.DEBUG)

    # dev = PingDevice(sys.argv[1])
    # dev.check()
    # print(dev._address)
    # print(dev._name)
    # print(dev._online)

    def evt_new(ping_device):
        assert isinstance(ping_device, PingDevice)
        print("Found new device [%s]" % ping_device.address)

    def evt_off(ping_device):
        assert isinstance(ping_device, PingDevice)
        print("Device [%s] disappeared" % ping_device.address)


    # callback = {'new': evt_new, 'off': evt_off}
    # devices = ['127.0.0.1', 'sensor', 'htc', 'access']

    logger = logging.getLogger()

    options = { 'sleep': 10,
                'timeout': 1,
                'psize': 64,
                'online': True,
                'callback': {'new': 'evt_new', 'off': evt_off},
                'devices': ['access','opti960','easybox']}

    devices =   {   'access':  {'dns': 'access', 'sleep': 1,  'online': False},
                    'opti960': {'dns': 'opti960', 'sleep': 1, 'online': False},
                    'easybox': {'dns': 'easybox', 'sleep': 10, 'online': True}
                }

    shutdown = False
    threads = []

    for device in options['devices']:

        if device not in devices:
            devices[device] = {}
            devices[device]['dns'] = device

        devices[device]['key'] = device

        for key in ['psize', 'timeout', 'sleep', 'callback', 'online']:
            if key in options:
                if key not in devices[device]:
                    devices[device][key] = options[key]

        thread = PingDiscoverDevice(logger, devices[device])
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

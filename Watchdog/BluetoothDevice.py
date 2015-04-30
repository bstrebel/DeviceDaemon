#!/usr/bin/env python

"""
    check devices by bluetooth address or hostname

"""
__version__ = "0.1"
__author__ = 'bst'

import bluetooth
import select
import re

from Device import *


class BluetoothDevice(Device):
    _pattern = re.compile("[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}")

    @staticmethod
    def _get_bt_name(address):
        for a, n in bluetooth.discover_devices(lookup_names=True):
            if a == address:
                return n
        return None

    @staticmethod
    def _get_bt_address(name):
        for a, n in bluetooth.discover_devices(lookup_names=True):
            if n == name:
                return a
        return None

    def __init__(self, *args, **kwargs):

        if self._pattern.match(args[0]):
            address = args[0]
            if len(args) == 1:
                name = self._get_bt_name(address)
            else:
                name = args[1]
        else:
            name = args[0]
            if len(args) == 1:
                address = self._get_bt_address(name)
            else:
                address = args[1]

        Device.__init__(self, address=address, name=name)

    def check(self, callback):
        if self._get_bt_name(self._address) is None:
            return False
        self.update()
        return True

    def age(self):
        age = time.time() - self._timestamp
        return age


class BluetoothDiscoverDevice(bluetooth.DeviceDiscoverer):
    def __init__(self, callback):
        self._done = False
        self._inquired = []
        self._devices = {}
        self._callback = callback
        bluetooth.DeviceDiscoverer.__init__(self)

    def pre_inquiry(self):
        self._done = False
        self._inquired = []

    def device_discovered(self, address, device_class, name):

        # try: self.devices
        # except AttributeError: self.devices = {}

        if address in self._devices:
            logging.debug("Update: %s" % name)
        else:
            logging.debug("New: %s" % name)
            self._devices[address] = BluetoothDevice(address, name)
            self._callback['new'](self._devices[address])

        self._devices[address].update()
        self._devices[address]._online = True
        self._inquired.append(address)

    def inquiry_complete(self):

        # try: self.devices
        # except AttributeError: self.devices = {}

        for addr, device in self._devices.items():
            if addr not in self._inquired:
                if device.online:
                    device.online = False
                    logging.debug("Off: %s" % device.name)
                    self._callback['off'](device)

        self._done = True

    def expired(self, seconds):

        # try: self.devices
        # except AttributeError: self.devices = {}

        for addr, device in self._devices.items():
            if device.age() > seconds:
                logging.debug("Expired: %s" % device.name)
                del device
                del self._devices[addr]


if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', level=logging.DEBUG)

    # dev = BluetoothDevice(sys.argv[1])
    # dev = BluetoothDevice('00:EE:BD:52:83:B5')
    # dev = BluetoothDevice('HTC One')
    # dev.check()
    # print(dev._address)
    # print(dev._name)

    def evt_new(bt_device):
        print("Found new device [%s]" % bt_device.address)

    def evt_off(bt_device):
        print("Device [%s] disappeared" % bt_device.address)

    callback = {'new': evt_new, 'off': evt_off}

    discover = BluetoothDiscoverDevice(callback)
    rf = [discover, ]
    discover.find_devices()

    while True:

        rfds = select.select(rf, [], [])[0]

        if discover in rfds:
            discover.process_event()

        if discover._done:
            time.sleep(1)
            discover.expired(30)
            discover.find_devices()

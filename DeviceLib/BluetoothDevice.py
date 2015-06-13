#!/usr/bin/env python

"""
    check devices by bluetooth address or hostname

"""
__version__ = "1.0"
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

        self._logger = args[0]
        
        if self._pattern.match(args[1]):
            address = args[1]
            if len(args) == 2:
                name = self._get_bt_name(address)
            else:
                name = args[2]
        else:
            name = args[1]
            if len(args) == 2:
                address = self._get_bt_address(name)
            else:
                address = args[2]

        Device.__init__(self, logger=self._logger, address=address, name=name)

    def check(self, callback):
        if self._get_bt_name(self._address) is None:
            return False
        self.update()
        return True


class BluetoothDiscoverDevice(bluetooth.DeviceDiscoverer):

    def __init__(self, options):
        
        self._logger = options['logger']
        self._callback = options['callback']
        
        self._done = False
        self._inquired = []
        self._devices = {}
        bluetooth.DeviceDiscoverer.__init__(self)

    def pre_inquiry(self):
        self._logger.debug("Starting bluetooth inquiry ...")
        self._done = False
        self._inquired = []

    def device_discovered(self, address, device_class, name):

        # try: self.devices
        # except AttributeError: self.devices = {}

        if address in self._devices:
            self._logger.debug("Bluetooth device update [%s] %s " % (address, name))
            pass
        else:
            # self._logger.debug("New: %s" % name)
            self._devices[address] = BluetoothDevice(self._logger, address, name)
            self._callback['new'](self._devices[address])

        self._devices[address].update()
        self._devices[address].online = True
        self._inquired.append(address)

    def inquiry_complete(self):

        # try: self.devices
        # except AttributeError: self.devices = {}

        self._logger.debug("Bluetooth inquiry completed")

        for addr, device in self._devices.items():
            if addr not in self._inquired:
                if device.online:
                    self._logger.debug("Off: %s" % device.name)
                    self._callback['off'](device)
                    device.online = False

        self._done = True

    def expired(self, seconds):

        # try: self.devices
        # except AttributeError: self.devices = {}

        for addr, device in self._devices.items():
            if device.age > seconds:
                self._logger.debug("Expired: %s" % device.name)
                del device
                del self._devices[addr]

    @property
    def done(self): return self._done


# region Main
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

    options = { 'logger': logging.getLogger(), 'expire': 30,
                'callback': {'new': evt_new, 'off': evt_off}}

    discover = BluetoothDiscoverDevice(options)
    rf = [discover, ]
    discover.find_devices()

    while True:

        rfds = select.select(rf, [], [])[0]

        if discover in rfds:
            discover.process_event()

        if discover._done:
            time.sleep(1)
            discover.expired(options['expire'])
            discover.find_devices()
# endregion

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

    def __init__(self, logger, device, name):

        self._logger = logger
        self._address = device['bt']
        self._name = name

        Device.__init__(self, logger, device)

    def check(self, callback):
        if self._get_bt_name(self._address) is None:
            return False
        self.update()
        return True

    @property
    def known(self): return self.config('key') != self.config('bt')

    @property
    def address(self): return self._address

    @property
    def name(self): return self._name


class BluetoothDiscoverDevice(bluetooth.DeviceDiscoverer):

    def __init__(self, logger, options, devices):
        
        bluetooth.DeviceDiscoverer.__init__(self)

        self._logger = logger
        self._callback = options['callback']
        
        self._done = False
        self._inquired = []

        self._known = {}
        for device in options['devices']:
            if device in devices and 'bt' in devices[device]:
                devices[device]['key'] = device
                self._known[devices[device]['bt']] = devices[device]

        self._devices = {}

    def pre_inquiry(self):
        self._logger.debug("Starting bluetooth inquiry ...")
        self._done = False
        self._inquired = []

    def device_discovered(self, address, device_class, name):

        self._inquired.append(address)

        if address in self._devices:
            self._logger.debug("Bluetooth device update [%s] %s " % (address, name))
            self._devices[address].update()
            self._devices[address].online = True
        else:
            self._logger.debug("Discovered [%s] %s" % (address, name))
            device = {}

            if address in self._known:
                device = self._known[address]
            else:
                device = {'key': address, 'bt': address, 'display': name}

            device['callback'] = self._callback

            self._devices[address] = BluetoothDevice(self._logger, device, name)
            self._devices[address].update()
            self._devices[address].online = True
            self._devices[address].callback('new')

    def inquiry_complete(self):

        self._logger.debug("Bluetooth inquiry completed")

        for addr, device in self._devices.items():
            if addr not in self._inquired:
                self._logger.debug("Offline [%s] %s" % ( device.address, device.name))
                if device.online:
                    device.online = False
                    device.callback('off')

        self._done = True

    def expired(self, seconds):

        # try: self.devices
        # except AttributeError: self.devices = {}

        for addr, device in self._devices.items():
            if device.age > seconds:
                self._logger.debug("Expired [%s] %s" % (device.address, device.name))
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
        assert isinstance(bt_device, BluetoothDevice)
        print("Found %s device [%s] %s" % ("known" if bt_device.known else "unknown",
                                           bt_device.address, bt_device.name))

    def evt_off(bt_device):
        assert isinstance(bt_device, BluetoothDevice)
        print("%s device [%s] %s disappeared" % ("Known" if bt_device.known else "Unknown",
                                                 bt_device.address, bt_device.name))

    logger = logging.getLogger()

    options = { 'expire': 60,
                'devices': ['nexus', 'htc'],
                'callback': {'new': evt_new, 'off': evt_off}}

    nexus = {

        'display': 'Google Nexus 10',
        'dns': 'nexus',
        'ip': '192.168.100.60',
        'serial': 'R32D102JR6N',
        'wlan': '08:d4:2b:17:d8:e8',
        'bt': '08:D4:2B:17:D8:E7',
        'online': False
    }

    htc = {

        'display': 'HTC One M7',
        'dns': 'htc',
        'ip': '192.168.2.50',
        'serial': 'SH42NW901328',
        'wlan': '50:2e:5c:cd:f4:54',
        'bt': '00:EE:BD:52:83:B5',
        'online': False
    }

    devices = {'nexus': nexus}

    discover = BluetoothDiscoverDevice(logger, options, devices)
    rf = [discover, ]
    discover.find_devices()

    while True:

        rfds = select.select(rf, [], [])[0]

        if discover in rfds:

            discover.process_event()

            if discover.done:
                # time.sleep(1)
                discover.expired(options['expire'])
                discover.find_devices()
# endregion

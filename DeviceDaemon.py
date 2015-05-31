#!/usr/bin/env python

"""
    DeviceLib Controller
    check devices by bluetooth address or hostname

"""

__version__ = "1.0"
__author__ = 'bst'

import os
import sys
import signal
import select
import logging
import logging.config
import argparse
import ConfigParser
import pprint

import daemon

from DeviceLib.BluetoothDevice import BluetoothDiscoverDevice, BluetoothDevice
from DeviceLib.PingDevice import PingDiscoverDevice, PingDevice

class Controller():

    def bluetooth_new(self, bt_device):
        assert isinstance(bt_device, BluetoothDevice)
        self._logger.info('Found new bluetooth device [%s] %s' % (bt_device.address, bt_device.name))

    def bluetooth_off(self, bt_device):
        assert isinstance(bt_device, BluetoothDevice)
        self._logger.info('Bluetooth device disappeared [%s] %s' % (bt_device.address, bt_device.name))

    def ping_new(self, ping_device):
        assert isinstance(ping_device, PingDevice)
        if ping_device.online is None:
            # device found by the first check after daemon starts
            self._logger.info('Found ip device [%s] %s' % (ping_device.address, ping_device.name))
        else:
            self._logger.info("Found new ip device [%s] %s" % (ping_device.address, ping_device.name))

    def ping_off(self, ping_device):
        assert isinstance(ping_device, PingDevice)
        if ping_device.online is None:
            # device offline during first check after daemon starts
            self._logger.info('IP device offline [%s] %s' % (ping_device.address, ping_device.name))
        else:
            self._logger.info('IP device disappeared [%s] %s' % (ping_device.address, ping_device.name))

    def __init__(self, options):

        self._options = options
        self._logger = options['controller']['logger']
        self._logger.debug("Controller constructor ...")

        self._root = options['controller']['root']

        self._ping = options['ping']
        self._ping['callback'] = {'new': self.ping_new, 'off': self.ping_off}
        self._ping['logger'] = self._logger

        self._bluetooth = options['bluetooth']
        self._bluetooth['callback'] = {'new': self.bluetooth_new, 'off': self.bluetooth_off}
        self._bluetooth['logger'] = self._logger


    def init(self):
        self._logger.info("Controller init ...")

        self._ping['discover'] = PingDiscoverDevice(self._ping )
        self._bluetooth['discover'] = BluetoothDiscoverDevice(self._bluetooth)


    def run(self):

        rf = [self._bluetooth['discover'], ]
        self._bluetooth['discover'].find_devices()

        while True:

            rfds = select.select(rf, [], [])[0]

            if self._bluetooth['discover'] in rfds:
                self._bluetooth['discover'].process_event()

            if self._bluetooth['discover'].done:
                # time.sleep(1)
                self._bluetooth['discover'].expired(30)
                self._bluetooth['discover'].find_devices()

            self._ping['discover'].discover()


    # signal handler called with signal number and stack frame
    def reload(self, *args):
        self._logger.info("Controller reload ...")
        self._logger.debug(args)

    def exit(self, *args):
        self._logger.info("Controller exit ...")
        exit(0)

    @property
    def options(self): return self._options

    @property
    def logger(self): return self._logger

    @property
    def root(self): return self._root

def daemonize(controller):

    # search log file handle: preserve file handler
    handle = None
    for handle in controller.logger.handlers:
        if type(handle) is logging.FileHandler:
            break

    if handle and type(handle) is logging.FileHandler and handle.stream:
        # preserve log file handler and redirect stdout/stderr to logfile
        _preserve = [handle.stream]
        _stdout = handle.stream
        _stderr = handle.stream
    else:
        _preserve = None
        _stdout = None
        _stderr = None

    # search log file handle: close console handlers
    handle = None
    for handle in controller.logger.handlers:
        if type(handle) is logging.StreamHandler:
            controller.logger.removeHandler(handle)


    context = daemon.DaemonContext(working_directory=controller.root,
                                   files_preserve=_preserve,
                                   stdout=_stdout,
                                   stderr=_stderr,
                                   detach_process=True)

    context.signal_map = {
        signal.SIGTERM: controller.exit,
        signal.SIGUSR1: controller.reload,
    }

    with context:
        controller.run()

def main():

    home = os.path.expanduser('~')
    root = home + '/DeviceDaemon'

    defaults = {}
    options = {}

    # command line arguments
    parser = argparse.ArgumentParser(description='Python Device Daemon Rev. 0.1 (c) Bernd Strebel')
    parser.add_argument('-v', '--verbose', action='count', help='increasy verbosity')
    parser.add_argument('-D', '--Daemon', action='store_true', help='run in background')
    parser.add_argument('-r', '--root', type=str, help='daemon root directory')
    parser.add_argument('-c', '--config', type=str, help='alternate configuration file')
    parser.add_argument('-i', '--ignore', action='store_true', help='ignore default configuration file(s)')
    parser.add_argument(      '--log', type=str, help='alternate logging configuration file')
    parser.add_argument('-l', '--loglevel', type=str,
                        choices=['DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'CRITICAL',
                                 'debug', 'info', 'warn', 'warning', 'error', 'critical'],
                        help='debug log level')

    args = parser.parse_args()

    root = os.getenv('DEVICE_DAEMON_CONTROLLER_ROOT', root)
    if args.root:
        root = args.root

    try:
        os.chdir(root)
    except os.error:
        sys.stderr.write("Invalid root directory [{0}]. Aborting ...".format(root))
        exit(1)

    defaults['controller'] = {'home': home,
                              'root': root,
                              'config': ['/etc/DeviceDaemon.cfg',
                                         root + '/controller.cfg',
                                         home + '/.DeviceDaemon.cfg'],
                              'log': root + '/logging.cfg',
                              'loglevel': 'DEBUG',
                              'Daemon': False,
                              }

    defaults['bluetooth'] = {'expire': 30}
    defaults['ping'] = {'devices': '127.0.0.1'}
    defaults['pir'] = {}

    # read configuration files
    config = ConfigParser.ConfigParser()
    if args.ignore:
        defaults['controller']['config'] = []

    if args.config:
        defaults['controller']['config'].append(args.config)

    config.read(defaults['controller']['config'])

    # get options from environment and/or configuration files
    for sec in defaults:
        options[sec] = {}
        for key in defaults[sec]:
            options[sec][key] = os.getenv('DEVICE_DAEMON_' + sec.upper() + '_' + key.upper(), defaults[sec][key])
            if config.has_section(sec):
                if config.has_option(sec,key):
                    options[sec][key] = config.get(sec,key)

    options['ping']['devices'] = options['ping']['devices'].split(',')

    # initialize logging from configuration file settings
    if args.log:
        options['controller']['log'] = args.log

    if args.loglevel:
        options['controller']['loglevel'] = args.loglevel

    if os.path.isfile(options['controller']['log']):
        logging.config.fileConfig(options['controller']['log'])
    else:
        logging.basicConfig(format='%(levelname)-7s %(message)s',
                            level=logging.DEBUG)

    logger = logging.getLogger('controller')
    options['controller']['logger'] = logger

    new_level = getattr(logging, options['controller']['loglevel'].upper(), None)
    if new_level:
        logger.setLevel(new_level)

    if args.Daemon:

        options['controller']['Daemon'] = True

        # search log file handle: close console handlers
        handle = None
        for handle in logger.handlers:
            if type(handle) is logging.StreamHandler:
                logger.removeHandler(handle)

        # sys.stderr.write("Running DeviceDaemon in background ...\n")


    logger.info("Initializing device demon [%s] ..." % os.path.basename(sys.argv[0]))
    logger.info("args: %s" % ' '.join(sys.argv[1:]))

    pp = pprint.PrettyPrinter()
    logger.info(pp.pformat(options))

    controller = Controller(options)
    controller.init()

    if options['controller']['Daemon']:
        daemonize(controller)
    else:
        try:
            controller.run()
        except KeyboardInterrupt:
            sys.stderr.write("\n")
            controller.exit()

    exit(0)

# region __Main__
if __name__ == '__main__':
    main()


    """
    home = os.path.expanduser("~") + "/.DeviceDaemon"
    logfile = {'name': home + "/controller.log", 'handle': None}
    detach = False
    context = False
    loglevel = logging.DEBUG

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s',
                        level=loglevel)

    logger = logging.getLogger()
    logfile['handle'] = logger.handlers[0].stream

    for section in config.sections():
        print(section)
        print(config.options(section))

    if args.loglevel:
        options['controller']['loglevel'] = args.loglevel

    import pprint
    pp = pprint.PrettyPrinter()
    pp.pprint(options)

    print(options)

    logger.info("Device daemon started")
    print(sys.argv[1:])

    controller = Controller(home, logger)


    """
# endregion

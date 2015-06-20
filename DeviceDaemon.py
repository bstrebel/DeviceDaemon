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
from ConfigParser import SafeConfigParser
import pprint
import time

# requires package python-daemon
import daemon

from DeviceLib.Device import Device
from DeviceLib.BluetoothDevice import BluetoothDiscoverDevice, BluetoothDevice
from DeviceLib.PingDevice import PingDiscoverDevice, PingDevice
from DeviceLib.HttpDevice import HttpDiscoverDevice, HttpDevice, HttpRequestHandler

class DefaultConfigParser(SafeConfigParser):

    def __init__(self, defaults):

        self._section_defaults = defaults;
        SafeConfigParser.__init__(self, allow_no_value=True)

    def get(self, section, option):

        if not self.has_section(section) and section in self._section_defaults:
            self.add_section(section)

        if not self.has_option(section, option) and option in self._section_defaults[section]:
            try:
                self.set(section, option, self._section_defaults[section][option])
            except:
                return self._section_defaults[section][option]

        value = SafeConfigParser.get(self, section, option)
        delimiter = ','

        if isinstance(self._section_defaults[section][option], list):
            return value.split(delimiter)
        else:
            return value

class PipeRequest:

    def __init__(self, logger, options):

        self._logger = logger
        self._callback = options['callback']
        self._fifo_name = options['path']
        self._fifo = None
        self._buffer = None

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
            if self._buffer:
                self._callback['request'](self._buffer)

        # return self._buffer

    @property
    def fifo(self): return self._fifo

    @property
    def fifo_name(self): return self._fifo_name


class Controller():

    def callback(self, device):
        assert(isinstance(device,Device))
        self._logger.warn("Generic callback for device [%s]. Check configuration!" % device.key)

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
            self._logger.info('Found ip device [%s] %s' % (ping_device.ip, ping_device.dns))
        else:
            self._logger.info("Found new ip device [%s] %s" % (ping_device.ip, ping_device.dns))

    def ping_off(self, ping_device):
        assert isinstance(ping_device, PingDevice)
        if ping_device.online is None:
            # device offline during first check after daemon starts
            self._logger.info('IP device offline [%s] %s' % (ping_device.ip, ping_device.dns))
        else:
            self._logger.info('IP device disappeared [%s] %s' % (ping_device.ip, ping_device.dns))

    def http_zone_changed(self, http_device):
        assert isinstance(http_device, HttpDevice)
        message = "Device %s with serial %s %s zone %s" %\
                  (http_device.name, http_device.serial,"entered" if http_device.update else "left", http_device.zone)
        self._logger.info(message)
        return 200, message

    def http_get_request(self, request, handler):
        assert isinstance(handler, HttpRequestHandler)
        self._logger("Http request: [%s]" % handler.path)
        return 200, "Path: %s" % handler.path

    def pipe_request(self, buffer):
        assert isinstance(buffer, str)
        self._logger.info("Pipe request: [%s]" % buffer)

    def __init__(self, logger, options, devices):

        self._logger = logger
        self._options = options
        self._devices = devices

        self._logger.debug("Controller constructor ...")

        self._root = options['controller']['root']

        self._ping = options['ping']
        self._ping['logger'] = self._logger
        self._ping['callback'] = {'new': self.ping_new, 'off': self.ping_off}

        self._bluetooth = options['bluetooth']
        self._bluetooth['logger'] = self._logger
        self._bluetooth['callback'] = {'new': self.bluetooth_new, 'off': self.bluetooth_off}

        self._pipe = options['pipe']
        self._pipe['logger'] = self._logger
        self._pipe['callback'] = {'request': self.pipe_request}

        self._http = options['http']
        self._http['logger'] = self._logger
        self._http['callback'] = {'update': self.http_zone_changed, 'request': self.http_get_request}

    def init(self):

        self._logger.info("Controller init ...")

        self._ping['discover'] = PingDiscoverDevice(self._logger, self._ping, self._devices)
        self._bluetooth['discover'] = BluetoothDiscoverDevice(self._logger, self._bluetooth, self._devices)

        self._http['discover'] = HttpDiscoverDevice(self._logger, self._http, self._devices)

        self._pipe['discover'] = PipeRequest(self._logger, self._pipe)

    def run(self):

        self._pipe['discover'].listen()

        self._ping['discover'].listen()
        self._http['discover'].listen()

        rf = [self._bluetooth['discover'], self._pipe['discover'].fifo, self._http['discover'].socket, ]
        self._bluetooth['discover'].find_devices()

        while True:

            rfds = select.select(rf, [], [])[0]

            if self._pipe['discover'].fifo in rfds:
                self._pipe['discover'].process_get_request()

            if self._http['discover'].socket in rfds:
                self._http['discover'].httpd.handle_request()

            if self._bluetooth['discover'] in rfds:
                self._bluetooth['discover'].process_event()

            if self._bluetooth['discover'].done:
                # time.sleep(1)
                self._bluetooth['discover'].expired(self._bluetooth['expire'])
                self._bluetooth['discover'].find_devices()


    # signal handler called with signal number and stack frame
    def reload(self, *args):
        self._logger.info("Controller reload ...")
        self._logger.debug(args)

    def exit(self, *args):
        self._logger.info("Controller exit ...")
        self._ping['discover'].shutdown()
        self._pipe['discover'].close()
        self._http['discover'].close()
        exit(0)

    def request(self, *args):
        pass

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

    def callback(self, device):
        assert(isinstance(device,Device))
        self._logger.warn("Generic callback for device [%s]. Check configuration!" % device.key)

    home = os.path.expanduser('~')
    root = home + '/DeviceDaemon'

    defaults = {}
    options = {}
    devices = {}

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

    controller = {'home': home,
                  'root': root,
                  'config': ['/etc/DeviceDaemon.cfg',
                             root + '/controller.cfg',
                             home + '/.DeviceDaemon.cfg'],
                  'log': root + '/logging.cfg',
                  'dev': root + '/devices.cfg',
                  'loglevel': 'DEBUG',
                  'Daemon': False}

    bluetooth = {'expire': 30,
                 'devices': []}

    ping = {'sleep': 10,
            'timeout': 1,
            'psize': 64,
            'online': True,
            'devices': []}

    http = {'host': '0.0.0.0',
            'port': 8080,
            'key': 'serial',
            'devices': []}

    pipe = {'path': '/tmp/DeviceDaemon.fifo'}
    pir = {}

    defaults = {'controller': controller,
                'bluetooth': bluetooth,
                'ping': ping,
                'http': http,
                'pipe': pipe,
                'pir': pir}

    # read configuration files
    config = DefaultConfigParser(defaults)
    if args.ignore:
        defaults['controller']['config'] = []

    if args.config:
        defaults['controller']['config'].append(args.config)

    config.read(defaults['controller']['config'])

    # get options from environment and/or configuration files
    for sec in defaults:
        options[sec] = {}
        for key in defaults[sec]:
            environment = os.getenv('DEVICE_DAEMON_' + sec.upper() + '_' + key.upper(), defaults[sec][key])
            options[sec][key] = environment if environment else config.get(sec, key)

    # get device configuration options
    dev_cfg = SafeConfigParser()
    dev_cfg.read(options['controller']['dev'])
    for sec in dev_cfg.sections():
        devices[sec] = {}
        for opt in dev_cfg.options(sec):
            devices[sec][opt] = dev_cfg.get(sec,opt)

    #        if config.has_section(sec):
    #            if config.has_option(sec,key):
    #                options[sec][key] = config.get(sec,key)

    # check an convert bluetooth expiration time
    # if config.has_section('bluetooth') and config.has_option('bluetooth', 'expire'):
    #    options['bluetooth']['expire'] = int(config.get('bluetooth', 'expire'))

    # create array from option string
    # _ping_devices = options['ping']['devices'].split(',')
    # options['ping']['devices'] = {}

    # create device hash from options
    # _http_devices = options['http']['devices'].split(',')
    # options['http']['devices'] = {}
    # for dev in _http_devices:
    #     if config.has_section('http') and config.has_option('http', dev):
    #         options['http']['devices'][dev] = config.get('http', dev)

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
    # options['controller']['logger'] = logger

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

    controller = Controller(logger, options, devices)
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

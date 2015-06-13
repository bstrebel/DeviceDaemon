#!/usr/bin/env python

"""
    check devices by ip address or hostname

"""
__version__ = "1.0"
__author__ = 'bst'

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import threading
import select

from urlparse import urlparse, parse_qs
# import time
# import os
# import select
# import subprocess
# import re
# import socket

from Device import *


class HttpDevice(Device):
    def __init__(self, logger, serial, name):
        self._logger = logger
        Device.__init__(self, logger=self._logger, address=serial, name=name)

    def check(self, callback):
        return True

    @property
    def serial(self): return self._address


class HttpRequestHandler(BaseHTTPRequestHandler):

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        # OPTS= self.server.options
        GET = parse_qs(urlparse(self.path).query)
        if GET:
            (response,message) = self.server.discover.process_get_request(GET, self)
            self.send_response(response)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(message)
            self.wfile.write('\n')
            self.wfile.write(threading.current_thread().getName())
            self.wfile.write('\n')

class HttpServer(ThreadingMixIn, HTTPServer):
    """
    Helper class to pass options to the request handler
    """

    def __init__(self, server, handler, discover):
        self.discover = discover
        HTTPServer.__init__(self, server, handler)

        # @property
        # def options(self): return self._options


class HttpDiscoverDevice:

    _update = {'0': 0, 'exit': 0, 'leave': 0, 'left': 0, 'out': '0', 'checkout': '0',
               '1': 1, 'enter': 1, 'entered': 1, 'in': 1, 'checkin': 1}

    # @staticmethod
    # def update(key):
    #     return {'0': 0, 'exit': 0, 'leave': 0, 'out': '0',
    #             '1': 1, 'enter': 1, 'in': 1}[key]

    def __init__(self, options):

        self._logger = options['logger']
        self._callback = options['callback']
        self._port = int(options['port'])
        self._host = options['host']
        self._httpd = None
        self._socket = None
        self._devices = {}

        for key in options['devices']:
            self._devices[key] = HttpDevice(self._logger, key, options['devices'][key])

    def process_get_request(self, request, handler):
        assert isinstance(handler, HttpRequestHandler)
        if 'device' in request and len(request['device']) == 1:
            key = request['device'][0]
            if key in self._devices:
                if 'zone' in request and len(request['zone']) == 1:
                    zone = request['zone'][0]
                    if 'update' in request and len(request['update']) == 1:
                        update = request['update'][0]
                        if update in self._update:
                            self._devices[key].zone = zone
                            self._devices[key].update = self._update[update]
                            return self._callback['update'](self._devices[key])

        return self._callback['request'](request, handler)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def listen(self):
        if self._httpd is not None:
            self.close()

        self._httpd = HttpServer((self._host, self._port), HttpRequestHandler, self)
        self._socket = self._httpd.socket;

        # self._httpd.serve_forever()
        return self._httpd.socket

        # rf = [self._httpd.socket, ]
        # while True:
        #     rfds = select.select(rf, [], [])[0]
        #     if self._httpd.socket in rfds:
        #         self._httpd.handle_request()


    def close(self):
        if self._httpd is not None:
            self._httpd.server_close()
            self._httpd = None

    @property
    def httpd(self):
        return self._httpd

    @property
    def socket(self):
        return self._socket

# region __Main__
if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', level=logging.DEBUG)

    def http_zone_changed(http_device):
        assert isinstance(http_device, HttpDevice)
        #print("Device %s with serial %s %s zone %s" % http_device.name,
        #      http_device.serial, "entered" if http_device.update else "left", http_device.zone)

        message = "Device %s with serial %s %s zone %s" %\
                  (http_device.name, http_device.serial,"entered" if http_device.update else "left", http_device.zone)

        return 200, message

    def request(request, handler):
        assert isinstance(handler, HttpRequestHandler)
        return 200, "Path: %s" % (handler.path)

    options = {'logger': logging.getLogger(),
               'host': '0.0.0.0',
               'port': 8080,
               'devices': {'R32D102JR6N': "Nexus 10", 'SH42NW901328': "HTC One"},
               'callback': {'update': http_zone_changed, 'request': request}}

    with HttpDiscoverDevice(options) as discover:

        try:

            socket = discover.listen()
            rf = [socket, ]
            while True:
                rfds = select.select(rf, [], [])[0]
                if socket in rfds:
                    discover._httpd.handle_request()

        except KeyboardInterrupt:
            discover.close()
            exit(0)



# endregion
